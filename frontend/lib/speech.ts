/**
 * Speech-to-Text (STT) and Text-to-Speech (TTS) Browser Integration
 * Free-first, zero-infrastructure speech client using standard Web Speech APIs.
 *
 * M27.1 Voice Recovery:
 * - Deterministic lifecycle state machines for Recognition, Synthesis, and Voice Chat.
 * - Prevents Chromium SpeechSynthesisUtterance GC bug via pinned utterance reference set.
 * - Long text chunking to prevent browser speech synthesis timeouts.
 * - Endpointing and silence detection to avoid premature single-word submissions.
 * - Safe tool approval pause (WAITING_FOR_APPROVAL) preventing accidental voice execution.
 * - MediaRecorder fallback helper for server-side transcription when Web Speech API is absent.
 */

export type VoiceMode = "TEXT" | "DICTATION" | "LISTEN" | "VOICE_CONVERSATION";

export type RecognitionState =
  | "UNSUPPORTED"
  | "IDLE"
  | "STARTING"
  | "LISTENING"
  | "FINALIZING"
  | "STOPPING"
  | "ERROR";

export type SynthesisState =
  | "IDLE"
  | "STARTING"
  | "SPEAKING"
  | "PAUSED"
  | "STOPPING"
  | "ERROR";

export type VoiceSessionState =
  | "INACTIVE"
  | "READY"
  | "STARTING"
  | "LISTENING"
  | "TRANSCRIBING"
  | "SUBMITTING"
  | "THINKING"
  | "WAITING_FOR_APPROVAL"
  | "SPEAKING"
  | "PAUSED"
  | "ERROR";

export interface SpeechVoiceOption {
  name: string;
  lang: string;
  default: boolean;
}

export interface TranscriptResult {
  finalTranscript: string;
  interimTranscript: string;
  fullTranscript: string;
  isFinal: boolean;
}

export interface RecognitionErrorInfo {
  code: string;
  message: string;
  isFatal: boolean;
  needsUserAction: boolean;
}

/**
 * Sanitizes markdown, citations, URLs, tables, and code blocks from text
 * so that synthesis reads aloud clean, natural sentences.
 */
export function cleanTextForSpeech(rawText: string): string {
  if (!rawText) return "";

  let cleaned = rawText;

  // 1. Remove markdown code blocks (```code```)
  cleaned = cleaned.replace(/```[\s\S]*?```/g, " ");

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
 * Splits text into safe, bite-sized sentence chunks (<= 200 characters)
 * to avoid browser speech synthesis hanging on long utterances.
 */
export function chunkTextForSpeech(text: string, maxChunkLength: number = 200): string[] {
  const clean = cleanTextForSpeech(text);
  if (!clean) return [];

  // Match sentences ending in punctuation
  const rawSentences = clean.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [clean];
  const chunks: string[] = [];

  for (const sentence of rawSentences) {
    const trimmed = sentence.trim();
    if (!trimmed) continue;

    if (trimmed.length <= maxChunkLength) {
      chunks.push(trimmed);
    } else {
      // Split by clauses (commas, semicolons, colons)
      const clauses = trimmed.split(/([,;:]\s+)/);
      let currentChunk = "";
      for (const clause of clauses) {
        if ((currentChunk + clause).length <= maxChunkLength) {
          currentChunk += clause;
        } else {
          if (currentChunk.trim()) {
            chunks.push(currentChunk.trim());
          }
          // If a single clause itself exceeds maxChunkLength, split by words
          if (clause.length > maxChunkLength) {
            const words = clause.split(/\s+/);
            let wordChunk = "";
            for (const word of words) {
              if ((wordChunk + " " + word).trim().length <= maxChunkLength) {
                wordChunk = (wordChunk + " " + word).trim();
              } else {
                if (wordChunk) chunks.push(wordChunk);
                wordChunk = word;
              }
            }
            currentChunk = wordChunk;
          } else {
            currentChunk = clause;
          }
        }
      }
      if (currentChunk.trim()) {
        chunks.push(currentChunk.trim());
      }
    }
  }

  return chunks.length > 0 ? chunks : [clean];
}

/**
 * Map browser speech recognition error codes to user-friendly explanations.
 */
export function mapRecognitionError(errCode: string): RecognitionErrorInfo {
  switch (errCode) {
    case "not-allowed":
      return {
        code: errCode,
        message: "Microphone access was denied. Please allow microphone permissions in your browser.",
        isFatal: true,
        needsUserAction: true,
      };
    case "service-not-allowed":
      return {
        code: errCode,
        message: "Speech recognition service is disabled or blocked by your browser.",
        isFatal: true,
        needsUserAction: true,
      };
    case "audio-capture":
      return {
        code: errCode,
        message: "No microphone detected or microphone is in use by another application.",
        isFatal: true,
        needsUserAction: true,
      };
    case "network":
      return {
        code: errCode,
        message: "Network error during speech recognition. Check your internet connection.",
        isFatal: false,
        needsUserAction: false,
      };
    case "no-speech":
      return {
        code: errCode,
        message: "No speech detected. Please speak into your microphone.",
        isFatal: false,
        needsUserAction: false,
      };
    case "language-not-supported":
      return {
        code: errCode,
        message: "The configured language is not supported by speech recognition.",
        isFatal: true,
        needsUserAction: true,
      };
    case "aborted":
      return {
        code: errCode,
        message: "Speech recognition was stopped.",
        isFatal: false,
        needsUserAction: false,
      };
    default:
      return {
        code: errCode,
        message: `Speech recognition error: ${errCode}`,
        isFatal: false,
        needsUserAction: false,
      };
  }
}

/**
 * Deterministic Browser Speech Recognition Controller.
 * Handles recognition lifecycle, separates interim from final transcripts,
 * and maintains accurate state transitions.
 */
export class BrowserSpeechRecognizer {
  private recognition: any = null;
  private state: RecognitionState = "IDLE";
  private desiredState: "IDLE" | "LISTENING" = "IDLE";

  private finalTranscript: string = "";
  private interimTranscript: string = "";

  private onTranscriptCallback: ((result: TranscriptResult) => void) | null = null;
  private onErrorCallback: ((error: RecognitionErrorInfo) => void) | null = null;
  private onStateCallback: ((state: RecognitionState) => void) | null = null;
  private onSpeechStartCallback: (() => void) | null = null;
  private onSpeechEndCallback: (() => void) | null = null;

  private lang: string = "en-US";
  private restartAttempts: number = 0;
  private maxRestartAttempts: number = 3;
  private restartTimeout: any = null;

  constructor(lang: string = "en-US") {
    this.lang = lang;
    this.initRecognition();
  }

  private initRecognition() {
    if (typeof window === "undefined") {
      this.state = "UNSUPPORTED";
      return;
    }

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      this.state = "UNSUPPORTED";
      return;
    }

    try {
      this.recognition = new SpeechRecognition();
      this.recognition.continuous = true;
      this.recognition.interimResults = true;
      this.recognition.lang = this.lang;

      // Real onstart callback: transition to LISTENING
      this.recognition.onstart = () => {
        this.restartAttempts = 0;
        this.setState("LISTENING");
      };

      if ("onaudiostart" in this.recognition) {
        this.recognition.onaudiostart = () => {};
      }

      this.recognition.onspeechstart = () => {
        if (this.onSpeechStartCallback) {
          this.onSpeechStartCallback();
        }
      };

      this.recognition.onspeechend = () => {
        if (this.onSpeechEndCallback) {
          this.onSpeechEndCallback();
        }
      };

      this.recognition.onresult = (event: any) => {
        let accumulatedFinal = "";
        let currentInterim = "";

        for (let i = 0; i < event.results.length; ++i) {
          const item = event.results[i];
          if (!item || !item[0]) continue;
          const text = item[0].transcript;

          if (item.isFinal) {
            const trimmed = text.trim();
            if (trimmed) {
              accumulatedFinal += (accumulatedFinal ? " " : "") + trimmed;
            }
          } else {
            currentInterim += text;
          }
        }

        this.finalTranscript = accumulatedFinal;
        this.interimTranscript = currentInterim;

        const full = (
          this.finalTranscript + (currentInterim ? " " + currentInterim.trim() : "")
        ).replace(/\s+/g, " ").trim();

        if (this.onTranscriptCallback) {
          this.onTranscriptCallback({
            finalTranscript: this.finalTranscript,
            interimTranscript: this.interimTranscript,
            fullTranscript: full,
            isFinal: Boolean(this.finalTranscript && !this.interimTranscript),
          });
        }
      };

      this.recognition.onerror = (event: any) => {
        const errCode = event.error || "unknown";
        const errInfo = mapRecognitionError(errCode);

        // Discard silent no-speech pauses
        if (errCode === "no-speech") {
          return;
        }

        if (errInfo.isFatal) {
          this.desiredState = "IDLE";
        }

        this.setState("ERROR");

        if (this.onErrorCallback) {
          this.onErrorCallback(errInfo);
        }
      };

      this.recognition.onend = () => {
        // Bounded restart only if user explicitly wants listening and error was not fatal
        if (this.desiredState === "LISTENING" && this.state !== "ERROR") {
          if (this.restartAttempts < this.maxRestartAttempts) {
            this.restartAttempts++;
            this.clearRestartTimer();
            this.restartTimeout = setTimeout(() => {
              if (this.desiredState === "LISTENING") {
                try {
                  this.recognition.start();
                } catch (_) {}
              }
            }, 300);
            return;
          }
        }

        this.desiredState = "IDLE";
        this.clearRestartTimer();
        if (this.state !== "ERROR") {
          this.setState("IDLE");
        }
      };

      this.state = "IDLE";
    } catch (_) {
      this.state = "UNSUPPORTED";
    }
  }

  private clearRestartTimer() {
    if (this.restartTimeout) {
      clearTimeout(this.restartTimeout);
      this.restartTimeout = null;
    }
  }

  private setState(newState: RecognitionState) {
    if (this.state === newState) return;
    this.state = newState;
    if (this.onStateCallback) {
      this.onStateCallback(newState);
    }
  }

  public getState(): RecognitionState {
    return this.state;
  }

  public isSupported(): boolean {
    return Boolean(this.recognition);
  }

  public getFinalTranscript(): string {
    return this.finalTranscript;
  }

  public getInterimTranscript(): string {
    return this.interimTranscript;
  }

  public clearTranscripts() {
    this.finalTranscript = "";
    this.interimTranscript = "";
  }

  public setLanguage(lang: string) {
    this.lang = lang;
    if (this.recognition) {
      this.recognition.lang = lang;
    }
  }

  public onTranscript(callback: (transcript: string, isFinal: boolean) => void): void;
  public onTranscript(callback: (result: TranscriptResult) => void): void;
  public onTranscript(
    callback: ((transcript: string, isFinal: boolean) => void) | ((result: TranscriptResult) => void)
  ) {
    this.onTranscriptCallback = (res: TranscriptResult) => {
      if (callback.length > 1) {
        (callback as (t: string, f: boolean) => void)(res.fullTranscript, res.isFinal);
      } else {
        (callback as (r: TranscriptResult) => void)(res);
      }
    };
  }

  public onError(callback: (error: string) => void): void;
  public onError(callback: (error: RecognitionErrorInfo) => void): void;
  public onError(
    callback: ((error: string) => void) | ((error: RecognitionErrorInfo) => void)
  ) {
    this.onErrorCallback = (err: RecognitionErrorInfo) => {
      (callback as (e: any) => void)(err.message);
    };
  }

  public onStateChange(callback: (isListening: boolean) => void): void;
  public onStateChange(callback: (state: RecognitionState) => void): void;
  public onStateChange(
    callback: ((isListening: boolean) => void) | ((state: RecognitionState) => void)
  ) {
    this.onStateCallback = (st: RecognitionState) => {
      (callback as (s: any) => void)(st === "LISTENING");
    };
  }

  public onState(callback: (state: RecognitionState) => void) {
    this.onStateCallback = callback;
  }

  public onSpeechStart(callback: () => void) {
    this.onSpeechStartCallback = callback;
  }

  public onSpeechEnd(callback: () => void) {
    this.onSpeechEndCallback = callback;
  }

  public start(): boolean {
    if (!this.recognition) {
      this.setState("UNSUPPORTED");
      return false;
    }

    if (this.state === "LISTENING" || this.state === "STARTING") {
      return true;
    }

    this.clearTranscripts();
    this.clearRestartTimer();
    this.restartAttempts = 0;
    this.desiredState = "LISTENING";
    this.setState("STARTING");

    try {
      this.recognition.start();
      return true;
    } catch (err: any) {
      if (err.name === "InvalidStateError") {
        // Recognition already running
        this.setState("LISTENING");
        return true;
      }
      this.desiredState = "IDLE";
      this.setState("ERROR");
      if (this.onErrorCallback) {
        this.onErrorCallback({
          code: err.name || "start-error",
          message: err.message || "Could not start microphone.",
          isFatal: true,
          needsUserAction: true,
        });
      }
      return false;
    }
  }

  public stop() {
    this.desiredState = "IDLE";
    this.clearRestartTimer();
    if (this.recognition && (this.state === "LISTENING" || this.state === "STARTING")) {
      this.setState("STOPPING");
      try {
        this.recognition.stop();
      } catch (_) {}
    } else {
      this.setState("IDLE");
    }
  }

  public abort() {
    this.desiredState = "IDLE";
    this.clearRestartTimer();
    if (this.recognition) {
      try {
        this.recognition.abort();
      } catch (_) {}
    }
    this.clearTranscripts();
    this.setState("IDLE");
  }
}

/**
 * Deterministic Browser Speech Synthesizer Controller.
 * Features:
 * - Persistent active utterance pinning to prevent Chromium GC bug.
 * - Long text chunking into sequential utterances to prevent freeze.
 * - Dynamic voiceschanged discovery with fallback.
 * - Test voice utility for operator manual testing.
 */
export class BrowserSpeechSynthesizer {
  private voices: SpeechSynthesisVoice[] = [];
  private state: SynthesisState = "IDLE";
  private onSpeakingChangeCallback: ((speaking: boolean) => void) | null = null;
  private onStateCallback: ((state: SynthesisState) => void) | null = null;

  // Active utterance set pinned to module instance to prevent Chromium GC
  private activeUtterances: Set<SpeechSynthesisUtterance> = new Set();
  private isProcessingQueue: boolean = false;
  private utteranceQueue: SpeechSynthesisUtterance[] = [];
  private currentOnEnd: (() => void) | null = null;
  private currentOnError: ((err: any) => void) | null = null;

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

  private setState(newState: SynthesisState) {
    if (this.state === newState) return;
    this.state = newState;
    if (this.onStateCallback) {
      this.onStateCallback(newState);
    }
    if (this.onSpeakingChangeCallback) {
      this.onSpeakingChangeCallback(newState === "SPEAKING");
    }
  }

  public getState(): SynthesisState {
    return this.state;
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

  public onState(callback: (state: SynthesisState) => void) {
    this.onStateCallback = callback;
  }

  /**
   * Speak clean text. Automatically chunks long messages into sequential utterances.
   */
  public speak(
    text: string,
    options?: {
      voiceName?: string;
      rate?: number;
      pitch?: number;
      lang?: string;
      onStart?: () => void;
      onEnd?: () => void;
      onError?: (err: any) => void;
    }
  ) {
    if (!this.isSupported()) {
      if (options?.onError) options.onError(new Error("Speech synthesis not supported in this browser"));
      return;
    }

    // Cancel any ongoing speech
    this.cancel();

    const chunks = chunkTextForSpeech(text);
    if (chunks.length === 0) {
      if (options?.onEnd) options.onEnd();
      return;
    }

    if (this.voices.length === 0) {
      this.loadVoices();
    }

    const matchedVoice = options?.voiceName
      ? this.voices.find((v) => v.name === options.voiceName)
      : undefined;

    this.currentOnEnd = options?.onEnd || null;
    this.currentOnError = options?.onError || null;

    const UtteranceConstructor =
      (typeof window !== "undefined" && (window as any).SpeechSynthesisUtterance) ||
      (globalThis as any).SpeechSynthesisUtterance;

    // Create queued utterances
    this.utteranceQueue = chunks.map((chunk, index) => {
      const utt = new UtteranceConstructor(chunk);
      utt.rate = options?.rate ?? 1.0;
      utt.pitch = options?.pitch ?? 1.0;
      if (options?.lang) utt.lang = options?.lang;
      if (matchedVoice) utt.voice = matchedVoice;

      // Pinned reference
      this.activeUtterances.add(utt);

      if (index === 0) {
        utt.onstart = () => {
          this.setState("SPEAKING");
          if (options?.onStart) options.onStart();
        };
      }

      utt.onend = () => {
        this.activeUtterances.delete(utt);
        this.playNextChunk();
      };

      utt.onerror = (err: any) => {
        this.activeUtterances.delete(utt);
        // Abort remainder of queue on error
        this.utteranceQueue = [];
        this.setState("ERROR");
        if (this.currentOnError) {
          this.currentOnError(err);
        }
      };

      return utt;
    });

    this.setState("STARTING");
    this.isProcessingQueue = true;
    this.playNextChunk();
  }

  private playNextChunk() {
    if (!this.isProcessingQueue || typeof window === "undefined" || !("speechSynthesis" in window)) {
      return;
    }

    if (this.utteranceQueue.length === 0) {
      this.isProcessingQueue = false;
      this.setState("IDLE");
      if (this.currentOnEnd) {
        const cb = this.currentOnEnd;
        this.currentOnEnd = null;
        cb();
      }
      return;
    }

    const nextUtt = this.utteranceQueue.shift();
    if (nextUtt) {
      try {
        window.speechSynthesis.speak(nextUtt);
      } catch (e) {
        this.activeUtterances.delete(nextUtt);
        this.setState("ERROR");
        if (this.currentOnError) this.currentOnError(e);
      }
    }
  }

  public pause() {
    if (this.isSupported() && window.speechSynthesis.speaking) {
      window.speechSynthesis.pause();
      this.setState("PAUSED");
    }
  }

  public resume() {
    if (this.isSupported() && window.speechSynthesis.paused) {
      window.speechSynthesis.resume();
      this.setState("SPEAKING");
    }
  }

  public cancel() {
    this.isProcessingQueue = false;
    this.utteranceQueue = [];
    this.activeUtterances.clear();
    this.currentOnEnd = null;
    this.currentOnError = null;

    if (this.isSupported()) {
      try {
        window.speechSynthesis.cancel();
      } catch (_) {}
    }

    this.setState("IDLE");
  }

  public isSpeaking(): boolean {
    return this.state === "SPEAKING" || (this.isSupported() ? window.speechSynthesis.speaking : false);
  }

  /**
   * Diagnostic test voice playback.
   */
  public testVoice(
    voiceName?: string,
    onComplete?: () => void
  ): boolean {
    if (!this.isSupported()) return false;
    const sample = "Hello! Speech synthesis is operating properly in your browser.";
    this.speak(sample, {
      voiceName,
      onEnd: onComplete,
      onError: onComplete,
    });
    return true;
  }
}

/**
 * Functional Turn-Based Voice Chat Session Controller.
 * Coordinates speech recognition, silence endpointing, turn submission locks,
 * tool approval pausing, and automated assistant reply synthesis.
 */
export class VoiceSessionController {
  private recognizer: BrowserSpeechRecognizer;
  private synthesizer: BrowserSpeechSynthesizer;
  private state: VoiceSessionState = "INACTIVE";

  private sessionId: string = "";
  private silenceTimer: any = null;
  private silenceTimeoutMs: number = 1200;
  private lastConfirmedTranscript: string = "";

  private onStateCallback: ((state: VoiceSessionState) => void) | null = null;
  private onTranscriptCallback: ((transcript: string, isFinal: boolean) => void) | null = null;
  private onTurnSubmit: ((transcript: string) => Promise<void>) | null = null;
  private isSubmitting: boolean = false;

  constructor(
    recognizer?: BrowserSpeechRecognizer,
    synthesizer?: BrowserSpeechSynthesizer
  ) {
    this.recognizer = recognizer || new BrowserSpeechRecognizer("en-US");
    this.synthesizer = synthesizer || new BrowserSpeechSynthesizer();
    this.bindEvents();
  }

  private bindEvents() {
    this.recognizer.onState((recState) => {
      if (recState === "LISTENING" && this.state !== "SPEAKING" && this.state !== "WAITING_FOR_APPROVAL") {
        this.setState("LISTENING");
      } else if (recState === "ERROR" && this.state !== "INACTIVE") {
        this.setState("ERROR");
      }
    });

    this.recognizer.onTranscript((result: TranscriptResult | string) => {
      if (this.state !== "LISTENING" && this.state !== "TRANSCRIBING") {
        return;
      }

      const res = typeof result === "string"
        ? { fullTranscript: result, isFinal: false, finalTranscript: result, interimTranscript: "" }
        : result;

      const text = res.fullTranscript.trim();
      if (!text) return;

      this.lastConfirmedTranscript = text;
      this.setState("TRANSCRIBING");

      if (this.onTranscriptCallback) {
        this.onTranscriptCallback(text, res.isFinal);
      }

      // Endpointing: reset silence timer
      this.resetSilenceTimer();
      this.silenceTimer = setTimeout(() => {
        this.handleSilenceTimeout();
      }, this.silenceTimeoutMs);
    });

    this.recognizer.onSpeechEnd(() => {
      // If user finished speech, accelerate silence endpointing
      if (this.lastConfirmedTranscript && !this.isSubmitting) {
        this.resetSilenceTimer();
        this.silenceTimer = setTimeout(() => {
          this.handleSilenceTimeout();
        }, 600);
      }
    });

    this.synthesizer.onState((synthState) => {
      if (synthState === "SPEAKING") {
        this.setState("SPEAKING");
      } else if (synthState === "IDLE" && this.state === "SPEAKING") {
        this.handleSynthesisComplete();
      }
    });
  }

  private resetSilenceTimer() {
    if (this.silenceTimer) {
      clearTimeout(this.silenceTimer);
      this.silenceTimer = null;
    }
  }

  private setState(newState: VoiceSessionState) {
    if (this.state === newState) return;
    this.state = newState;
    if (this.onStateCallback) {
      this.onStateCallback(newState);
    }
  }

  private async handleSilenceTimeout() {
    this.resetSilenceTimer();
    const candidate = this.lastConfirmedTranscript.trim();

    if (!candidate || this.isSubmitting || this.state === "WAITING_FOR_APPROVAL") {
      return;
    }

    this.isSubmitting = true;
    this.setState("SUBMITTING");

    // Stop microphone while processing turn
    this.recognizer.stop();

    try {
      this.setState("THINKING");
      if (this.onTurnSubmit) {
        await this.onTurnSubmit(candidate);
      }
    } catch (_) {
      this.setState("ERROR");
    } finally {
      this.isSubmitting = false;
      this.lastConfirmedTranscript = "";
      this.recognizer.clearTranscripts();
    }
  }

  private handleSynthesisComplete() {
    // If waiting for tool approval or inactive, stay in that state
    if (this.state === "WAITING_FOR_APPROVAL" || this.state === "INACTIVE") {
      return;
    }

    // Turn complete -> transition to READY and start next listening turn
    this.setState("READY");
    this.startListeningTurn();
  }

  public getState(): VoiceSessionState {
    return this.state;
  }

  public onStateChange(callback: (state: VoiceSessionState) => void) {
    this.onStateCallback = callback;
  }

  public onTranscript(callback: (transcript: string, isFinal: boolean) => void) {
    this.onTranscriptCallback = callback;
  }

  public setTurnSubmitHandler(handler: (transcript: string) => Promise<void>) {
    this.onTurnSubmit = handler;
  }

  public startSession(): boolean {
    this.sessionId = Math.random().toString(36).substring(2, 9);
    this.isSubmitting = false;
    this.lastConfirmedTranscript = "";
    this.recognizer.clearTranscripts();
    this.setState("READY");
    return this.startListeningTurn();
  }

  public startListeningTurn(): boolean {
    if (this.state === "WAITING_FOR_APPROVAL") {
      return false;
    }
    this.resetSilenceTimer();
    this.lastConfirmedTranscript = "";
    this.recognizer.clearTranscripts();
    this.setState("STARTING");
    return this.recognizer.start();
  }

  public endSession() {
    this.sessionId = "";
    this.resetSilenceTimer();
    this.isSubmitting = false;
    this.lastConfirmedTranscript = "";
    this.recognizer.stop();
    this.synthesizer.cancel();
    this.setState("INACTIVE");
  }

  public pauseSession() {
    this.resetSilenceTimer();
    this.recognizer.stop();
    this.synthesizer.pause();
    this.setState("PAUSED");
  }

  public notifyWaitingForApproval() {
    this.resetSilenceTimer();
    this.recognizer.stop();
    this.synthesizer.cancel();
    this.setState("WAITING_FOR_APPROVAL");
  }

  public notifyApprovalResolved() {
    if (this.state === "WAITING_FOR_APPROVAL") {
      this.setState("READY");
      this.startListeningTurn();
    }
  }

  public speakResponse(text: string, onEnd?: () => void) {
    this.resetSilenceTimer();
    this.recognizer.stop();
    this.setState("SPEAKING");

    this.synthesizer.speak(text, {
      onEnd: () => {
        if (onEnd) onEnd();
        this.handleSynthesisComplete();
      },
      onError: () => {
        if (onEnd) onEnd();
        this.handleSynthesisComplete();
      },
    });
  }

  public stopAudio() {
    this.resetSilenceTimer();
    this.synthesizer.cancel();
    this.recognizer.stop();
    this.setState("READY");
  }
}

/**
 * Optional MediaRecorder audio capture fallback.
 * Can be used when SpeechRecognition is completely unsupported by the browser
 * to record bounded audio and send it to /api/v1/speech/transcribe.
 */
export class AudioRecorderFallback {
  private mediaRecorder: MediaRecorder | null = null;
  private audioChunks: Blob[] = [];
  private stream: MediaStream | null = null;
  private isRecording: boolean = false;

  public isSupported(): boolean {
    return (
      typeof window !== "undefined" &&
      typeof navigator !== "undefined" &&
      Boolean(navigator.mediaDevices?.getUserMedia) &&
      typeof MediaRecorder !== "undefined"
    );
  }

  public async startRecording(): Promise<boolean> {
    if (!this.isSupported()) return false;
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.audioChunks = [];
      this.mediaRecorder = new MediaRecorder(this.stream);

      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.audioChunks.push(event.data);
        }
      };

      this.mediaRecorder.start(250);
      this.isRecording = true;
      return true;
    } catch (_) {
      this.isRecording = false;
      return false;
    }
  }

  public stopRecording(): Promise<Blob | null> {
    return new Promise((resolve) => {
      if (!this.mediaRecorder || !this.isRecording) {
        resolve(null);
        return;
      }

      this.mediaRecorder.onstop = () => {
        const audioBlob = new Blob(this.audioChunks, {
          type: this.mediaRecorder?.mimeType || "audio/webm",
        });
        this.stream?.getTracks().forEach((track) => track.stop());
        this.stream = null;
        this.mediaRecorder = null;
        this.isRecording = false;
        resolve(audioBlob);
      };

      try {
        this.mediaRecorder.stop();
      } catch (_) {
        resolve(null);
      }
    });
  }

  public cancel() {
    if (this.mediaRecorder && this.isRecording) {
      try {
        this.mediaRecorder.stop();
      } catch (_) {}
    }
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
    this.mediaRecorder = null;
    this.isRecording = false;
    this.audioChunks = [];
  }
}
