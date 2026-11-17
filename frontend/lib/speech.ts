/**
 * Speech-to-Text (STT) and Text-to-Speech (TTS) Browser Integration
 * Free-first, zero-infrastructure speech client using standard Web Speech APIs.
 */

export type VoiceMode = "TEXT" | "DICTATION" | "LISTEN" | "VOICE_CONVERSATION";

export interface SpeechVoiceOption {
  name: string;
  lang: string;
  default: boolean;
}

/**
 * Sanitizes markdown, citations, URLs, and code blocks from text
 * so that synthesis reads aloud clean, natural sentences.
 */
export function cleanTextForSpeech(rawText: string): string {
  if (!rawText) return "";

  let cleaned = rawText;

  // 1. Remove markdown code blocks (```code```)
  cleaned = cleaned.replace(/```[\s\S]*?```/g, " [code block omitted] ");

  // 2. Remove inline code snippets (`code`)
  cleaned = cleaned.replace(/`([^`]+)`/g, "$1");

  // 3. Remove markdown links [title](url) -> keep title
  cleaned = cleaned.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");

  // 4. Remove standalone URLs
  cleaned = cleaned.replace(/https?:\/\/\S+/g, "");

  // 5. Remove numbered citations like [1], [2], [1, 2] and full-width citations 【1】, 【4】
  cleaned = cleaned.replace(/\[\d+(?:,\s*\d+)*\]/g, "");
  cleaned = cleaned.replace(/【\d+(?:,\s*\d+)*】/g, "");

  // 6. Remove markdown formatting characters (#, *, _, ~, >, |)
  cleaned = cleaned.replace(/^[#>\-\*\+]\s+/gm, "");
  cleaned = cleaned.replace(/(\*\*|__)(.*?)\1/g, "$2");
  cleaned = cleaned.replace(/(\*|_)(.*?)\1/g, "$2");
  cleaned = cleaned.replace(/~~(.*?)~~/g, "$1");

  // 7. Remove tables and divider lines
  cleaned = cleaned.replace(/\|/g, " ");
  cleaned = cleaned.replace(/-{3,}/g, " ");

  // 8. Collapse whitespace and trim
  cleaned = cleaned.replace(/\s+/g, " ").trim();

  return cleaned;
}

/**
 * Browser Speech Recognition wrapper (Web Speech API)
 */
export class BrowserSpeechRecognizer {
  private recognition: any = null;
  private isListening: boolean = false;
  private shouldBeListening: boolean = false;
  private onResultCallback: ((transcript: string, isFinal: boolean) => void) | null = null;
  private onErrorCallback: ((error: string) => void) | null = null;
  private onStateCallback: ((isListening: boolean) => void) | null = null;
  private lang: string = "en-US";
  private finalTranscriptBuffer: string = "";

  constructor(lang: string = "en-US") {
    this.lang = lang;
    if (typeof window !== "undefined") {
      const SpeechRecognition =
        (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (SpeechRecognition) {
        this.recognition = new SpeechRecognition();
        this.recognition.continuous = true;
        this.recognition.interimResults = true;
        this.recognition.lang = this.lang;

        this.recognition.onresult = (event: any) => {
          let currentInterim = "";

          for (let i = event.resultIndex; i < event.results.length; ++i) {
            const transcript = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
              this.finalTranscriptBuffer += (this.finalTranscriptBuffer ? " " : "") + transcript.trim();
            } else {
              currentInterim += transcript;
            }
          }

          const combined = (
            this.finalTranscriptBuffer + (currentInterim ? " " + currentInterim : "")
          ).trim();

          if (this.onResultCallback) {
            this.onResultCallback(combined, Boolean(this.finalTranscriptBuffer && !currentInterim));
          }
        };

        this.recognition.onerror = (event: any) => {
          const err = event.error || "Speech recognition error";
          // Ignore harmless pauses in speech
          if (err === "no-speech") {
            return;
          }
          if (this.onErrorCallback) {
            this.onErrorCallback(err);
          }
          if (err === "not-allowed" || err === "service-not-allowed" || err === "audio-capture") {
            this.shouldBeListening = false;
            this.setListening(false);
          }
        };

        this.recognition.onend = () => {
          // If we should still be listening (e.g. user paused speech), auto-restart recognition
          if (this.shouldBeListening) {
            try {
              this.recognition.start();
              return;
            } catch (_) {}
          }
          this.setListening(false);
        };
      }
    }
  }

  public isSupported(): boolean {
    return Boolean(this.recognition);
  }

  public setLanguage(lang: string) {
    this.lang = lang;
    if (this.recognition) {
      this.recognition.lang = lang;
    }
  }

  public onTranscript(callback: (transcript: string, isFinal: boolean) => void) {
    this.onResultCallback = callback;
  }

  public onError(callback: (error: string) => void) {
    this.onErrorCallback = callback;
  }

  public onStateChange(callback: (isListening: boolean) => void) {
    this.onStateCallback = callback;
  }

  public start(): boolean {
    if (!this.recognition) return false;
    this.finalTranscriptBuffer = "";
    this.shouldBeListening = true;

    try {
      this.recognition.start();
      this.setListening(true);
      return true;
    } catch (err: any) {
      // If already started, mark listening
      if (err.name === "InvalidStateError") {
        this.setListening(true);
        return true;
      }
      this.shouldBeListening = false;
      if (this.onErrorCallback) {
        this.onErrorCallback(err.message || "Failed to start microphone");
      }
      return false;
    }
  }

  public stop() {
    this.shouldBeListening = false;
    if (this.recognition) {
      try {
        this.recognition.stop();
      } catch (_) {}
      this.setListening(false);
    }
  }

  public abort() {
    this.shouldBeListening = false;
    if (this.recognition) {
      try {
        this.recognition.abort();
      } catch (_) {}
      this.setListening(false);
    }
  }

  private setListening(val: boolean) {
    this.isListening = val;
    if (this.onStateCallback) {
      this.onStateCallback(val);
    }
  }
}

/**
 * Browser Speech Synthesis wrapper (Web Speech API)
 */
export class BrowserSpeechSynthesizer {
  private voices: SpeechSynthesisVoice[] = [];
  private onSpeakingChangeCallback: ((speaking: boolean) => void) | null = null;
  private resumeTimer: any = null;

  constructor() {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      this.loadVoices();
      if (window.speechSynthesis.onvoiceschanged !== undefined) {
        window.speechSynthesis.onvoiceschanged = () => this.loadVoices();
      }
    }
  }

  private loadVoices() {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      this.voices = window.speechSynthesis.getVoices();
    }
  }

  public isSupported(): boolean {
    return typeof window !== "undefined" && "speechSynthesis" in window;
  }

  public getVoices(): SpeechSynthesisVoice[] {
    if (this.voices.length === 0 && typeof window !== "undefined" && "speechSynthesis" in window) {
      this.voices = window.speechSynthesis.getVoices();
    }
    return this.voices;
  }

  public onSpeakingChange(callback: (speaking: boolean) => void) {
    this.onSpeakingChangeCallback = callback;
  }

  public speak(
    text: string,
    options?: {
      voiceName?: string;
      rate?: number;
      pitch?: number;
      lang?: string;
      onEnd?: () => void;
      onError?: (err: any) => void;
    }
  ) {
    if (!this.isSupported()) {
      if (options?.onError) options.onError(new Error("Speech synthesis not supported"));
      return;
    }

    const clean = cleanTextForSpeech(text);
    if (!clean) {
      if (options?.onEnd) options.onEnd();
      return;
    }

    // Cancel existing utterance & clear heartbeat
    this.cancel();

    // Ensure voices are up to date
    if (this.voices.length === 0) {
      this.loadVoices();
    }

    const utterance = new SpeechSynthesisUtterance(clean);
    utterance.rate = options?.rate ?? 1.0;
    utterance.pitch = options?.pitch ?? 1.0;
    if (options?.lang) {
      utterance.lang = options?.lang;
    }

    if (options?.voiceName) {
      const match = this.voices.find((v) => v.name === options.voiceName);
      if (match) {
        utterance.voice = match;
      }
    }

    const cleanupHeartbeat = () => {
      if (this.resumeTimer) {
        clearInterval(this.resumeTimer);
        this.resumeTimer = null;
      }
    };

    utterance.onstart = () => {
      if (this.onSpeakingChangeCallback) this.onSpeakingChangeCallback(true);

      // Chrome long-utterance keepalive workaround:
      cleanupHeartbeat();
      this.resumeTimer = setInterval(() => {
        if (typeof window !== "undefined" && window.speechSynthesis && window.speechSynthesis.speaking) {
          window.speechSynthesis.pause();
          window.speechSynthesis.resume();
        } else {
          cleanupHeartbeat();
        }
      }, 10000);
    };

    utterance.onend = () => {
      cleanupHeartbeat();
      if (this.onSpeakingChangeCallback) this.onSpeakingChangeCallback(false);
      if (options?.onEnd) options.onEnd();
    };

    utterance.onerror = (err) => {
      cleanupHeartbeat();
      if (this.onSpeakingChangeCallback) this.onSpeakingChangeCallback(false);
      if (options?.onError) options.onError(err);
    };

    window.speechSynthesis.speak(utterance);
  }

  public pause() {
    if (this.isSupported()) {
      window.speechSynthesis.pause();
    }
  }

  public resume() {
    if (this.isSupported()) {
      window.speechSynthesis.resume();
    }
  }

  public cancel() {
    if (this.resumeTimer) {
      clearInterval(this.resumeTimer);
      this.resumeTimer = null;
    }
    if (this.isSupported()) {
      window.speechSynthesis.cancel();
      if (this.onSpeakingChangeCallback) this.onSpeakingChangeCallback(false);
    }
  }

  public isSpeaking(): boolean {
    return this.isSupported() ? window.speechSynthesis.speaking : false;
  }
}
