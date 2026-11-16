# M25.3 — Manual UI & Voice Acceptance Checklist

## Operator Manual Acceptance Instructions
Navigate to `https://mmaip-frontend.onrender.com/login` and log in with your credentials.

### Checklist:
1. **Chat Attachment Control**:
   - [ ] Open an active conversation.
   - [ ] Click the paperclip icon in the composer.
   - [ ] Select a sample document (PDF, TXT, DOCX, CSV).
   - [ ] Verify the file chip appears above the composer showing filename, size, and status `Ready`.
2. **Document-Grounded Chat**:
   - [ ] Ask a question regarding the contents of the attached document.
   - [ ] Verify that the assistant answers with grounded facts and citation tags.
   - [ ] Click a citation tag to inspect the chunk excerpt modal.
3. **Save to Knowledge Base**:
   - [ ] Click "Save to KB" on the attachment chip.
   - [ ] Select the target Knowledge Base and confirm.
   - [ ] Verify the chip reflects `Saved to KB`.
4. **Voice Mode Toggle**:
   - [ ] In the top right header, cycle through the modes:
     - `Text`: Normal keyboard interaction.
     - `Dictate`: Click the microphone icon, speak, and verify real-time interim and final transcript populates the textarea.
     - `Listen`: Send a question and verify the assistant's answer is read aloud via speech synthesis.
     - `Voice Chat`: Speak a message, observe automatic send, streaming response, and immediate spoken answer.
5. **Speech Controls**:
   - [ ] Click the speaker icon on any assistant card to play or pause the audio.
   - [ ] When audio is playing, click "Stop Speaking" in the status bar to verify speech cancellation.
6. **Agentic Tool Approval Safeguard**:
   - [ ] In Voice Chat mode, trigger an action requiring human approval.
   - [ ] Verify that voice playback halts and the interactive approval card appears.
   - [ ] Confirm that tool execution requires clicking "Approve & Execute" or "Deny".
