from enum import Enum


class TenantType(str, Enum):
    INDIVIDUAL = "INDIVIDUAL"
    ORGANIZATION = "ORGANIZATION"


class TenantStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    PENDING_DELETION = "PENDING_DELETION"


class MembershipStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INVITED = "INVITED"
    SUSPENDED = "SUSPENDED"


class UserStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"


class SystemRole(str, Enum):
    PLATFORM_SUPERADMIN = "platform_superadmin"
    TENANT_OWNER = "tenant_owner"
    ORG_ADMIN = "org_admin"
    DEPT_ADMIN = "dept_admin"
    ASSISTANT_MANAGER = "assistant_manager"
    KNOWLEDGE_EDITOR = "knowledge_editor"
    EMPLOYEE = "employee"
    VIEWER = "viewer"


class PermissionName(str, Enum):
    # Tenant Lifecycle
    TENANT_READ = "tenant.read"
    TENANT_UPDATE = "tenant.update"
    TENANT_DELETE = "tenant.delete"
    TENANT_BILLING = "tenant.billing"

    # Member & Employee Management
    MEMBER_INVITE = "member.invite"
    MEMBER_READ = "member.read"
    MEMBER_UPDATE = "member.update"
    MEMBER_REMOVE = "member.remove"

    # Department & Groups
    DEPARTMENT_CREATE = "department.create"
    DEPARTMENT_READ = "department.read"
    DEPARTMENT_UPDATE = "department.update"
    DEPARTMENT_DELETE = "department.delete"

    GROUP_CREATE = "group.create"
    GROUP_READ = "group.read"
    GROUP_UPDATE = "group.update"
    GROUP_DELETE = "group.delete"

    # Assistants
    ASSISTANT_CREATE = "assistant.create"
    ASSISTANT_READ = "assistant.read"
    ASSISTANT_UPDATE = "assistant.update"
    ASSISTANT_DELETE = "assistant.delete"
    ASSISTANT_EXECUTE = "assistant.execute"
    ASSISTANT_PUBLISH = "assistant.publish"

    # API Keys & Integration (M08)
    API_KEY_MANAGE = "api_key.manage"
    API_KEY_READ = "api_key.read"

    # Knowledge & Documents
    KNOWLEDGE_CREATE = "knowledge.create"
    KNOWLEDGE_READ = "knowledge.read"
    KNOWLEDGE_UPLOAD = "knowledge.upload"
    KNOWLEDGE_DELETE = "knowledge.delete"

    # Granular Document & Ingestion (Milestone 02)
    DOCUMENT_UPLOAD = "document.upload"
    DOCUMENT_READ = "document.read"
    DOCUMENT_DELETE = "document.delete"
    DOCUMENT_REPROCESS = "document.reprocess"
    DOCUMENT_READ_CONTENT = "document.read_content"
    DOCUMENT_READ_CHUNKS = "document.read_chunks"
    INGESTION_READ = "ingestion.read"
    INGESTION_RETRY = "ingestion.retry"
    INGESTION_CANCEL = "ingestion.cancel"
    INGESTION_CONFIGURE = "ingestion.configure"

    # Retrieval & Vector Search (Milestone 03)
    RETRIEVAL_SEARCH = "retrieval.search"
    RETRIEVAL_PREVIEW = "retrieval.preview"
    RETRIEVAL_CONFIGURE = "retrieval.configure"
    INDEX_READ = "index.read"
    INDEX_REINDEX = "index.reindex"

    # Conversations & Chat
    CONVERSATION_CREATE = "conversation.create"
    CONVERSATION_READ = "conversation.read"
    CONVERSATION_DELETE = "conversation.delete"

    # Audit & Administration
    AUDIT_READ = "audit.read"
    USAGE_READ = "usage.read"


# Mapping of initial system roles to granular permissions
ROLE_PERMISSIONS_MAP: dict[SystemRole, list[PermissionName]] = {
    SystemRole.PLATFORM_SUPERADMIN: list(PermissionName),
    SystemRole.TENANT_OWNER: [
        PermissionName.TENANT_READ,
        PermissionName.TENANT_UPDATE,
        PermissionName.TENANT_DELETE,
        PermissionName.TENANT_BILLING,
        PermissionName.MEMBER_INVITE,
        PermissionName.MEMBER_READ,
        PermissionName.MEMBER_UPDATE,
        PermissionName.MEMBER_REMOVE,
        PermissionName.DEPARTMENT_CREATE,
        PermissionName.DEPARTMENT_READ,
        PermissionName.DEPARTMENT_UPDATE,
        PermissionName.DEPARTMENT_DELETE,
        PermissionName.GROUP_CREATE,
        PermissionName.GROUP_READ,
        PermissionName.GROUP_UPDATE,
        PermissionName.GROUP_DELETE,
        PermissionName.ASSISTANT_CREATE,
        PermissionName.ASSISTANT_READ,
        PermissionName.ASSISTANT_UPDATE,
        PermissionName.ASSISTANT_DELETE,
        PermissionName.ASSISTANT_EXECUTE,
        PermissionName.KNOWLEDGE_CREATE,
        PermissionName.KNOWLEDGE_READ,
        PermissionName.KNOWLEDGE_UPLOAD,
        PermissionName.KNOWLEDGE_DELETE,
        PermissionName.DOCUMENT_UPLOAD,
        PermissionName.DOCUMENT_READ,
        PermissionName.DOCUMENT_DELETE,
        PermissionName.DOCUMENT_REPROCESS,
        PermissionName.DOCUMENT_READ_CONTENT,
        PermissionName.DOCUMENT_READ_CHUNKS,
        PermissionName.INGESTION_READ,
        PermissionName.INGESTION_RETRY,
        PermissionName.INGESTION_CANCEL,
        PermissionName.INGESTION_CONFIGURE,
        PermissionName.RETRIEVAL_SEARCH,
        PermissionName.RETRIEVAL_PREVIEW,
        PermissionName.RETRIEVAL_CONFIGURE,
        PermissionName.INDEX_READ,
        PermissionName.INDEX_REINDEX,
        PermissionName.CONVERSATION_CREATE,
        PermissionName.CONVERSATION_READ,
        PermissionName.CONVERSATION_DELETE,
        PermissionName.AUDIT_READ,
        PermissionName.USAGE_READ,
        PermissionName.ASSISTANT_PUBLISH,
        PermissionName.API_KEY_MANAGE,
        PermissionName.API_KEY_READ,
    ],
    SystemRole.ORG_ADMIN: [
        PermissionName.TENANT_READ,
        PermissionName.TENANT_UPDATE,
        PermissionName.MEMBER_INVITE,
        PermissionName.MEMBER_READ,
        PermissionName.MEMBER_UPDATE,
        PermissionName.MEMBER_REMOVE,
        PermissionName.DEPARTMENT_CREATE,
        PermissionName.DEPARTMENT_READ,
        PermissionName.DEPARTMENT_UPDATE,
        PermissionName.DEPARTMENT_DELETE,
        PermissionName.GROUP_CREATE,
        PermissionName.GROUP_READ,
        PermissionName.GROUP_UPDATE,
        PermissionName.GROUP_DELETE,
        PermissionName.ASSISTANT_CREATE,
        PermissionName.ASSISTANT_READ,
        PermissionName.ASSISTANT_UPDATE,
        PermissionName.ASSISTANT_EXECUTE,
        PermissionName.KNOWLEDGE_CREATE,
        PermissionName.KNOWLEDGE_READ,
        PermissionName.KNOWLEDGE_UPLOAD,
        PermissionName.DOCUMENT_UPLOAD,
        PermissionName.DOCUMENT_READ,
        PermissionName.DOCUMENT_DELETE,
        PermissionName.DOCUMENT_REPROCESS,
        PermissionName.DOCUMENT_READ_CONTENT,
        PermissionName.DOCUMENT_READ_CHUNKS,
        PermissionName.INGESTION_READ,
        PermissionName.INGESTION_RETRY,
        PermissionName.INGESTION_CANCEL,
        PermissionName.INGESTION_CONFIGURE,
        PermissionName.RETRIEVAL_SEARCH,
        PermissionName.RETRIEVAL_PREVIEW,
        PermissionName.RETRIEVAL_CONFIGURE,
        PermissionName.INDEX_READ,
        PermissionName.INDEX_REINDEX,
        PermissionName.CONVERSATION_CREATE,
        PermissionName.CONVERSATION_READ,
        PermissionName.CONVERSATION_DELETE,
        PermissionName.AUDIT_READ,
        PermissionName.USAGE_READ,
        PermissionName.ASSISTANT_PUBLISH,
        PermissionName.API_KEY_MANAGE,
        PermissionName.API_KEY_READ,
    ],
    SystemRole.DEPT_ADMIN: [
        PermissionName.TENANT_READ,
        PermissionName.MEMBER_READ,
        PermissionName.DEPARTMENT_READ,
        PermissionName.DEPARTMENT_UPDATE,
        PermissionName.GROUP_READ,
        PermissionName.ASSISTANT_READ,
        PermissionName.ASSISTANT_EXECUTE,
        PermissionName.KNOWLEDGE_READ,
        PermissionName.KNOWLEDGE_UPLOAD,
        PermissionName.DOCUMENT_UPLOAD,
        PermissionName.DOCUMENT_READ,
        PermissionName.DOCUMENT_READ_CONTENT,
        PermissionName.DOCUMENT_READ_CHUNKS,
        PermissionName.INGESTION_READ,
        PermissionName.INGESTION_RETRY,
        PermissionName.RETRIEVAL_SEARCH,
        PermissionName.RETRIEVAL_PREVIEW,
        PermissionName.INDEX_READ,
        PermissionName.CONVERSATION_CREATE,
        PermissionName.CONVERSATION_READ,
        PermissionName.CONVERSATION_DELETE,
    ],
    SystemRole.ASSISTANT_MANAGER: [
        PermissionName.TENANT_READ,
        PermissionName.ASSISTANT_CREATE,
        PermissionName.ASSISTANT_READ,
        PermissionName.ASSISTANT_UPDATE,
        PermissionName.ASSISTANT_DELETE,
        PermissionName.ASSISTANT_EXECUTE,
        PermissionName.KNOWLEDGE_READ,
        PermissionName.DOCUMENT_READ,
        PermissionName.DOCUMENT_READ_CONTENT,
        PermissionName.DOCUMENT_READ_CHUNKS,
        PermissionName.RETRIEVAL_SEARCH,
        PermissionName.RETRIEVAL_PREVIEW,
        PermissionName.INDEX_READ,
        PermissionName.CONVERSATION_CREATE,
        PermissionName.CONVERSATION_READ,
    ],
    SystemRole.KNOWLEDGE_EDITOR: [
        PermissionName.TENANT_READ,
        PermissionName.KNOWLEDGE_CREATE,
        PermissionName.KNOWLEDGE_READ,
        PermissionName.KNOWLEDGE_UPLOAD,
        PermissionName.KNOWLEDGE_DELETE,
        PermissionName.DOCUMENT_UPLOAD,
        PermissionName.DOCUMENT_READ,
        PermissionName.DOCUMENT_DELETE,
        PermissionName.DOCUMENT_REPROCESS,
        PermissionName.DOCUMENT_READ_CONTENT,
        PermissionName.DOCUMENT_READ_CHUNKS,
        PermissionName.INGESTION_READ,
        PermissionName.INGESTION_RETRY,
        PermissionName.INGESTION_CONFIGURE,
        PermissionName.RETRIEVAL_SEARCH,
        PermissionName.RETRIEVAL_PREVIEW,
        PermissionName.RETRIEVAL_CONFIGURE,
        PermissionName.INDEX_READ,
        PermissionName.INDEX_REINDEX,
        PermissionName.ASSISTANT_READ,
        PermissionName.CONVERSATION_CREATE,
        PermissionName.CONVERSATION_READ,
    ],
    SystemRole.EMPLOYEE: [
        PermissionName.TENANT_READ,
        PermissionName.MEMBER_READ,
        PermissionName.DEPARTMENT_READ,
        PermissionName.GROUP_READ,
        PermissionName.ASSISTANT_READ,
        PermissionName.ASSISTANT_EXECUTE,
        PermissionName.KNOWLEDGE_READ,
        PermissionName.DOCUMENT_READ,
        PermissionName.DOCUMENT_READ_CONTENT,
        PermissionName.DOCUMENT_READ_CHUNKS,
        PermissionName.INGESTION_READ,
        PermissionName.RETRIEVAL_SEARCH,
        PermissionName.CONVERSATION_CREATE,
        PermissionName.CONVERSATION_READ,
    ],
    SystemRole.VIEWER: [
        PermissionName.TENANT_READ,
        PermissionName.MEMBER_READ,
        PermissionName.DEPARTMENT_READ,
        PermissionName.GROUP_READ,
        PermissionName.ASSISTANT_READ,
        PermissionName.KNOWLEDGE_READ,
        PermissionName.DOCUMENT_READ,
        PermissionName.DOCUMENT_READ_CONTENT,
        PermissionName.DOCUMENT_READ_CHUNKS,
        PermissionName.RETRIEVAL_SEARCH,
        PermissionName.CONVERSATION_READ,
    ],
}
