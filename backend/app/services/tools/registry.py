"""Tool Registry Service layer for managing and executing Built-in and Custom HTTP tools."""

import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool import Tool
from app.services.tools.builtin import (
    BUILTIN_TOOL_DEFINITIONS,
    safe_calculate,
    synthetic_weather_lookup,
)
from app.services.tools.http_runner import execute_custom_http_tool
from app.services.tools.ssrf import validate_outbound_url



class ToolRegistryService:
    """Manages tool registration, schema discovery, and safe execution."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID, user_id: Optional[uuid.UUID] = None):
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id

    async def list_tools(self, tool_type: Optional[str] = None) -> list[dict[str, Any]]:
        """List all tools available to this tenant (Built-in + Custom HTTP + MCP)."""
        all_tools: list[dict[str, Any]] = []

        # 1. Built-in Tools
        if not tool_type or tool_type.upper() == "BUILTIN":
            for b in BUILTIN_TOOL_DEFINITIONS:
                all_tools.append({
                    "id": f"builtin_{b['name']}",
                    "name": b["name"],
                    "display_name": b["display_name"],
                    "description": b["description"],
                    "namespace": b["namespace"],
                    "tool_type": b["tool_type"],
                    "risk_level": b["risk_level"],
                    "requires_approval": b["requires_approval"],
                    "is_enabled": True,
                    "version": "1.0.0",
                    "input_schema": b["input_schema"],
                    "output_schema": b["output_schema"],
                    "http_config": {},
                })

        # 2. Database Registered Tools (Custom HTTP + MCP)
        stmt = (
            select(Tool)
            .where(Tool.tenant_id == self.tenant_id)
            .order_by(Tool.created_at.desc())
        )
        if tool_type and tool_type.upper() != "BUILTIN":
            stmt = stmt.where(Tool.tool_type == tool_type.upper())

        rows = (await self.session.execute(stmt)).scalars().all()
        for r in rows:
            all_tools.append({
                "id": str(r.id),
                "name": r.name,
                "display_name": r.display_name,
                "description": r.description,
                "namespace": r.namespace,
                "tool_type": r.tool_type,
                "risk_level": r.risk_level,
                "requires_approval": r.requires_approval,
                "is_enabled": r.is_enabled,
                "version": r.version,
                "input_schema": r.input_schema,
                "output_schema": r.output_schema,
                "http_config": r.http_config,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })

        return all_tools

    async def get_tool(self, tool_id_or_name: str) -> Optional[dict[str, Any]]:
        """Fetch a specific tool by ID or builtin name with strict tenant isolation."""
        # Built-in check
        for b in BUILTIN_TOOL_DEFINITIONS:
            if tool_id_or_name in (f"builtin_{b['name']}", b["name"]):
                return {
                    "id": f"builtin_{b['name']}",
                    "name": b["name"],
                    "display_name": b["display_name"],
                    "description": b["description"],
                    "namespace": b["namespace"],
                    "tool_type": b["tool_type"],
                    "risk_level": b["risk_level"],
                    "requires_approval": b["requires_approval"],
                    "is_enabled": True,
                    "version": "1.0.0",
                    "input_schema": b["input_schema"],
                    "output_schema": b["output_schema"],
                    "http_config": {},
                }

        # DB check
        try:
            t_uuid = uuid.UUID(tool_id_or_name)
            stmt = select(Tool).where(Tool.id == t_uuid, Tool.tenant_id == self.tenant_id)
        except (ValueError, TypeError):
            stmt = select(Tool).where(Tool.name == tool_id_or_name, Tool.tenant_id == self.tenant_id)

        record = (await self.session.execute(stmt)).scalar_one_or_none()
        if not record:
            return None

        return {
            "id": str(record.id),
            "name": record.name,
            "display_name": record.display_name,
            "description": record.description,
            "namespace": record.namespace,
            "tool_type": record.tool_type,
            "risk_level": record.risk_level,
            "requires_approval": record.requires_approval,
            "is_enabled": record.is_enabled,
            "version": record.version,
            "input_schema": record.input_schema,
            "output_schema": record.output_schema,
            "http_config": record.http_config,
            "timeout_seconds": record.timeout_seconds,
            "max_response_bytes": record.max_response_bytes,
        }

    async def create_custom_tool(
        self,
        name: str,
        display_name: str,
        endpoint_url: str,
        description: Optional[str] = None,
        method: str = "POST",
        input_schema: Optional[dict[str, Any]] = None,
        output_schema: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        risk_level: str = "READ_ONLY",
        requires_approval: bool = False,
        timeout_seconds: int = 15,
    ) -> Tool:
        """Register a new Custom HTTP tool with URL validation and schema bounds."""
        clean_name = name.strip().lower()

        # Check uniqueness
        stmt = select(Tool).where(Tool.tenant_id == self.tenant_id, Tool.name == clean_name)
        if (await self.session.execute(stmt)).scalar_one_or_none():
            raise ValueError(f"A tool named '{clean_name}' already exists in this workspace.")

        # Validate URL safety and SSRF upfront
        validated_url = validate_outbound_url(endpoint_url.strip())

        http_config = {
            "endpoint_url": validated_url,
            "method": method.upper().strip(),
            "headers": headers or {},
        }


        tool = Tool(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            name=clean_name,
            display_name=display_name.strip(),
            description=description.strip() if description else None,
            namespace="custom",
            tool_type="CUSTOM_HTTP",
            risk_level=risk_level,
            requires_approval=requires_approval,
            is_enabled=True,
            version="1.0.0",
            input_schema=input_schema or {"type": "object", "properties": {}},
            output_schema=output_schema or {"type": "object", "properties": {}},
            http_config=http_config,
            timeout_seconds=min(max(timeout_seconds, 1), 30),
        )

        self.session.add(tool)
        await self.session.commit()
        await self.session.refresh(tool)
        return tool

    async def execute_tool(
        self,
        tool_id_or_name: str,
        arguments: dict[str, Any],
        allow_http_for_testing: bool = False,
    ) -> dict[str, Any]:
        """Execute a tool (Builtin or Custom HTTP) with parameter binding and security checks."""
        # 1. Built-in calculator
        if tool_id_or_name in ("calculator", "builtin_calculator"):
            expression = str(arguments.get("expression", "")).strip()
            result = safe_calculate(expression)
            return {"result": result}

        # 2. Built-in weather lookup
        if tool_id_or_name in ("weather_lookup", "builtin_weather_lookup"):
            city = str(arguments.get("city", "London")).strip()
            return synthetic_weather_lookup(city)

        # 3. Custom HTTP tool
        tool = await self.get_tool(tool_id_or_name)
        if not tool:
            raise ValueError(f"Tool '{tool_id_or_name}' not found or unauthorized.")

        if not tool.get("is_enabled"):
            raise ValueError(f"Tool '{tool['name']}' is currently disabled.")

        if tool["tool_type"] == "CUSTOM_HTTP":
            cfg = tool.get("http_config", {})
            endpoint = cfg.get("endpoint_url", "")
            method = cfg.get("method", "POST")
            headers = cfg.get("headers", {})

            return await execute_custom_http_tool(
                endpoint_url=endpoint,
                method=method,
                headers=headers,
                body=arguments,
                timeout_seconds=tool.get("timeout_seconds", 15),
                max_response_bytes=tool.get("max_response_bytes", 1048576),
                allow_http_for_testing=allow_http_for_testing,
            )

        raise ValueError(f"Execution for tool type '{tool['tool_type']}' not supported in this runtime.")
