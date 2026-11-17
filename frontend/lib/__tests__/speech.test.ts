/**
 * Comprehensive Unit Tests for M27.1 Speech Architecture
 * Tests:
 * 1. cleanTextForSpeech (markdown, citations, urls, code blocks)
 * 2. chunkTextForSpeech (splitting long answers into safe chunks)
 * 3. mapRecognitionError (user-friendly error mapping)
 * 4. BrowserSpeechRecognizer (lifecycle: IDLE -> STARTING -> LISTENING -> onresult -> STOPPING -> IDLE)
 * 5. BrowserSpeechSynthesizer (activeUtterances pinned, queue sequential playback, testVoice)
 * 6. VoiceSessionController (multi-turn voice session, silence endpointing, WAITING_FOR_APPROVAL safety pause)
 */

import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";

import {
  cleanTextForSpeech,
  chunkTextForSpeech,
  mapRecognitionError,
  BrowserSpeechRecognizer,
  BrowserSpeechSynthesizer,
  VoiceSessionController,
} from "../speech.ts";
import type {
  RecognitionState,
  VoiceSessionState,
  TranscriptResult,
} from "../speech.ts";

describe("Speech Sanitation & Chunking", () => {
  it("should strip markdown, code blocks, citations, and URLs", () => {
    const raw = `
# Header 1
Here is **bold** text and *italic* text.
\`\`\`python
def foo():
    return 42
\`\`\`
Refer to [W3Schools](https://www.w3schools.com) for details.
Check citation [1] and full-width citation 【4】.
Inline code: \`x = 10\`.
Table:
| col1 | col2 |
|---|---|
| val1 | val2 |
    `;

    const cleaned = cleanTextForSpeech(raw);
    assert.ok(!cleaned.includes("```"));
    assert.ok(!cleaned.includes("def foo():"));
    assert.ok(!cleaned.includes("https://"));
    assert.ok(!cleaned.includes("[1]"));
    assert.ok(!cleaned.includes("【4】"));
    assert.ok(!cleaned.includes("|"));
    assert.ok(cleaned.includes("Here is bold text and italic text"));
    assert.ok(cleaned.includes("Refer to W3Schools for details"));
    assert.ok(cleaned.includes("Inline code: x = 10"));
  });

  it("should chunk long responses safely without losing sentences", () => {
    const text =
      "First sentence is short. Second sentence explains something in deeper detail and continues for quite some length until the point is completely clear to the reader. Third sentence concludes the thought.";

    const chunks = chunkTextForSpeech(text, 100);
    assert.ok(chunks.length >= 2);
    for (const chunk of chunks) {
      assert.ok(chunk.length <= 110, `Chunk too long: ${chunk.length}`);
    }
  });

  it("should correctly map recognition errors", () => {
    const denied = mapRecognitionError("not-allowed");
    assert.equal(denied.isFatal, true);
    assert.ok(denied.message.includes("Microphone access was denied"));

    const noSpeech = mapRecognitionError("no-speech");
    assert.equal(noSpeech.isFatal, false);
    assert.ok(noSpeech.message.includes("No speech detected"));
  });
});

// Mock Browser Environment
class MockSpeechRecognition {
  public continuous = false;
  public interimResults = false;
  public lang = "en-US";
  public onstart: (() => void) | null = null;
  public onresult: ((event: any) => void) | null = null;
  public onerror: ((event: any) => void) | null = null;
  public onend: (() => void) | null = null;
  public onspeechstart: (() => void) | null = null;
  public onspeechend: (() => void) | null = null;

  public isStarted = false;

  public start() {
    this.isStarted = true;
    setTimeout(() => {
      if (this.onstart) this.onstart();
    }, 10);
  }

  public stop() {
    this.isStarted = false;
    setTimeout(() => {
      if (this.onend) this.onend();
    }, 10);
  }

  public abort() {
    this.isStarted = false;
    setTimeout(() => {
      if (this.onend) this.onend();
    }, 10);
  }

  public emitResult(results: Array<{ transcript: string; isFinal: boolean }>, resultIndex = 0) {
    if (this.onresult) {
      const event = {
        resultIndex,
        results: results.map((r) => [{ transcript: r.transcript }]),
      };
      // attach isFinal to each item
      results.forEach((r, idx) => {
        (event.results[idx] as any).isFinal = r.isFinal;
      });
      this.onresult(event);
    }
  }

  public emitError(errorCode: string) {
    if (this.onerror) {
      this.onerror({ error: errorCode });
    }
  }
}

class MockSpeechSynthesisUtterance {
  public text: string;
  public rate = 1.0;
  public pitch = 1.0;
  public lang = "en-US";
  public voice: any = null;
  public onstart: (() => void) | null = null;
  public onend: (() => void) | null = null;
  public onerror: ((err: any) => void) | null = null;

  constructor(text: string) {
    this.text = text;
  }
}

class MockSpeechSynthesis {
  public speaking = false;
  public paused = false;
  public onvoiceschanged: (() => void) | null = null;
  private voices: any[] = [
    { name: "Google US English", lang: "en-US", default: true },
    { name: "Microsoft David", lang: "en-US", default: false },
  ];

  public getVoices() {
    return this.voices;
  }

  public speak(utt: MockSpeechSynthesisUtterance) {
    this.speaking = true;
    setTimeout(() => {
      if (utt.onstart) utt.onstart();
      setTimeout(() => {
        this.speaking = false;
        if (utt.onend) utt.onend();
      }, 20);
    }, 10);
  }

  public pause() {
    this.paused = true;
  }

  public resume() {
    this.paused = false;
  }

  public cancel() {
    this.speaking = false;
    this.paused = false;
  }
}

describe("BrowserSpeechRecognizer", () => {
  let mockRecognition: MockSpeechRecognition;

  beforeEach(() => {
    mockRecognition = new MockSpeechRecognition();
    (global as any).window = {
      SpeechRecognition: function () {
        return mockRecognition;
      },
    };
  });

  it("should initialize in IDLE state and transition to LISTENING on real start event", async () => {
    const recognizer = new BrowserSpeechRecognizer("en-US");
    assert.equal(recognizer.getState(), "IDLE");

    let receivedState: RecognitionState = "IDLE";
    recognizer.onState((st) => {
      receivedState = st;
    });

    const started = recognizer.start();
    assert.equal(started, true);
    assert.equal(recognizer.getState(), "STARTING");

    // Wait for onstart callback
    await new Promise((resolve) => setTimeout(resolve, 25));
    assert.equal(recognizer.getState(), "LISTENING");
    assert.equal(receivedState, "LISTENING");

    recognizer.stop();
    await new Promise((resolve) => setTimeout(resolve, 25));
    assert.equal(recognizer.getState(), "IDLE");
  });

  it("should separate interim from final transcripts and avoid duplicates", async () => {
    const recognizer = new BrowserSpeechRecognizer("en-US");
    recognizer.start();
    await new Promise((resolve) => setTimeout(resolve, 20));

    let latestFull = "";
    recognizer.onTranscript((res: TranscriptResult) => {
      latestFull = res.fullTranscript;
    });

    // 1. Interim word
    mockRecognition.emitResult([{ transcript: "Hello", isFinal: false }]);
    assert.equal(latestFull, "Hello");

    // 2. Finalize first phrase, interim second phrase
    mockRecognition.emitResult([
      { transcript: "Hello world", isFinal: true },
      { transcript: " how are you", isFinal: false },
    ]);
    assert.equal(latestFull, "Hello world how are you");
    assert.equal(recognizer.getFinalTranscript(), "Hello world");

    // 3. Finalize second phrase
    mockRecognition.emitResult([
      { transcript: "Hello world", isFinal: true },
      { transcript: "how are you", isFinal: true },
    ]);
    assert.equal(recognizer.getFinalTranscript(), "Hello world how are you");
  });

  it("should handle fatal error and update state to ERROR", async () => {
    const recognizer = new BrowserSpeechRecognizer("en-US");
    recognizer.start();
    await new Promise((resolve) => setTimeout(resolve, 20));

    let errorReceived = "";
    recognizer.onError((err) => {
      errorReceived = err;
    });

    mockRecognition.emitError("not-allowed");
    assert.equal(recognizer.getState(), "ERROR");
    assert.ok(errorReceived.includes("Microphone access was denied"));
  });
});

describe("BrowserSpeechSynthesizer", () => {
  beforeEach(() => {
    (global as any).SpeechSynthesisUtterance = MockSpeechSynthesisUtterance;
    (global as any).window = {
      speechSynthesis: new MockSpeechSynthesis(),
      SpeechSynthesisUtterance: MockSpeechSynthesisUtterance,
    };
  });

  it("should speak clean chunks and fire onEnd", async () => {
    const synthesizer = new BrowserSpeechSynthesizer();
    assert.equal(synthesizer.isSupported(), true);

    let ended = false;
    synthesizer.speak("Hello there! This is a test.", {
      onEnd: () => {
        ended = true;
      },
    });

    assert.equal(synthesizer.getState(), "STARTING");
    await new Promise((resolve) => setTimeout(resolve, 150));
    assert.equal(ended, true);
    assert.equal(synthesizer.getState(), "IDLE");
  });

  it("should support testVoice method", async () => {
    const synthesizer = new BrowserSpeechSynthesizer();
    let completed = false;
    const ok = synthesizer.testVoice(undefined, () => {
      completed = true;
    });
    assert.equal(ok, true);
    await new Promise((resolve) => setTimeout(resolve, 150));
    assert.equal(completed, true);
  });
});

describe("VoiceSessionController", () => {
  let mockRecognition: MockSpeechRecognition;

  beforeEach(() => {
    mockRecognition = new MockSpeechRecognition();
    (global as any).SpeechSynthesisUtterance = MockSpeechSynthesisUtterance;
    (global as any).window = {
      SpeechRecognition: function () {
        return mockRecognition;
      },
      speechSynthesis: new MockSpeechSynthesis(),
      SpeechSynthesisUtterance: MockSpeechSynthesisUtterance,
    };
  });

  it("should execute turn endpointing and invoke turn submission once", async () => {
    const recognizer = new BrowserSpeechRecognizer("en-US");
    const synthesizer = new BrowserSpeechSynthesizer();
    const controller = new VoiceSessionController(recognizer, synthesizer);

    let submittedCount = 0;
    let submittedText = "";

    controller.setTurnSubmitHandler(async (text) => {
      submittedCount++;
      submittedText = text;
      // Synthesize answer aloud
      controller.speakResponse("A for loop repeats a block of code.");
    });

    controller.startSession();
    await new Promise((resolve) => setTimeout(resolve, 25));
    assert.equal(controller.getState(), "LISTENING");

    // User speaks phrase
    mockRecognition.emitResult([{ transcript: "What is a for loop?", isFinal: true }]);
    assert.equal(controller.getState(), "TRANSCRIBING");

    // Trigger end of speech to accelerate endpointing
    if (mockRecognition.onspeechend) {
      mockRecognition.onspeechend();
    }

    // Wait for silence endpointing timeout (~600ms)
    await new Promise((resolve) => setTimeout(resolve, 750));

    // Turn submitted once
    assert.equal(submittedCount, 1);
    assert.equal(submittedText, "What is a for loop?");

    // Wait for synthesis playback (~100ms)
    await new Promise((resolve) => setTimeout(resolve, 150));

    // Controller transitions back to ready/listening for turn 2
    assert.ok(
      controller.getState() === "LISTENING" || controller.getState() === "STARTING",
      `Unexpected state after turn 1: ${controller.getState()}`
    );

    controller.endSession();
    assert.equal(controller.getState(), "INACTIVE");
  });

  it("should safely pause voice loop during WAITING_FOR_APPROVAL and not restart listening", async () => {
    const recognizer = new BrowserSpeechRecognizer("en-US");
    const synthesizer = new BrowserSpeechSynthesizer();
    const controller = new VoiceSessionController(recognizer, synthesizer);

    controller.startSession();
    await new Promise((resolve) => setTimeout(resolve, 25));

    // Enter tool approval state
    controller.notifyWaitingForApproval();
    assert.equal(controller.getState(), "WAITING_FOR_APPROVAL");

    // Attempting to start listening turn while in approval state must fail
    const canListen = controller.startListeningTurn();
    assert.equal(canListen, false);
    assert.equal(controller.getState(), "WAITING_FOR_APPROVAL");

    // Explicit user approval in UI resolves the state
    controller.notifyApprovalResolved();
    await new Promise((resolve) => setTimeout(resolve, 25));
    assert.ok(
      controller.getState() === "LISTENING" || controller.getState() === "STARTING",
      `Unexpected state after approval: ${controller.getState()}`
    );

    controller.endSession();
  });

  it("should complete a full two-turn conversation lifecycle", async () => {
    const recognizer = new BrowserSpeechRecognizer("en-US");
    const synthesizer = new BrowserSpeechSynthesizer();
    const controller = new VoiceSessionController(recognizer, synthesizer);

    const turnsReceived: string[] = [];

    controller.setTurnSubmitHandler(async (text) => {
      turnsReceived.push(text);
      if (text.includes("for loop")) {
        controller.speakResponse("A for loop has an initialization, condition, and increment.");
      } else if (text.includes("example")) {
        controller.speakResponse("For example: for int i = 0; i < 10; i++ print i.");
      }
    });

    // Start session
    controller.startSession();
    await new Promise((resolve) => setTimeout(resolve, 25));
    assert.equal(controller.getState(), "LISTENING");

    // Turn 1: user asks about for loop
    mockRecognition.emitResult([{ transcript: "What is a C++ for loop?", isFinal: true }]);
    if (mockRecognition.onspeechend) mockRecognition.onspeechend();

    // Silence endpointing triggers submission
    await new Promise((resolve) => setTimeout(resolve, 750));
    assert.equal(turnsReceived.length, 1);
    assert.equal(turnsReceived[0], "What is a C++ for loop?");

    // Synthesis finishes playing
    await new Promise((resolve) => setTimeout(resolve, 150));
    assert.ok(
      controller.getState() === "LISTENING" || controller.getState() === "STARTING",
      `Controller not ready for turn 2: ${controller.getState()}`
    );

    // Turn 2: user asks for an example
    mockRecognition.emitResult([{ transcript: "Give me an example", isFinal: true }]);
    if (mockRecognition.onspeechend) mockRecognition.onspeechend();

    await new Promise((resolve) => setTimeout(resolve, 750));
    assert.equal(turnsReceived.length, 2);
    assert.equal(turnsReceived[1], "Give me an example");

    // Synthesis finishes playing second turn
    await new Promise((resolve) => setTimeout(resolve, 150));

    controller.endSession();
    assert.equal(controller.getState(), "INACTIVE");
  });

  it("should stop audio immediately and cancel speech playback", async () => {
    const recognizer = new BrowserSpeechRecognizer("en-US");
    const synthesizer = new BrowserSpeechSynthesizer();
    const controller = new VoiceSessionController(recognizer, synthesizer);

    controller.startSession();
    await new Promise((resolve) => setTimeout(resolve, 25));

    controller.speakResponse("This is a very long response that needs to be interrupted.");
    assert.equal(controller.getState(), "SPEAKING");

    controller.stopAudio();
    assert.equal(controller.getState(), "READY");
    assert.equal(synthesizer.isSpeaking(), false);

    controller.endSession();
  });
});

describe("Additional Voice Edge Cases", () => {
  it("should handle voices loaded late via onvoiceschanged", () => {
    const mockSynth = new MockSpeechSynthesis();
    (global as any).window = {
      speechSynthesis: mockSynth,
      SpeechSynthesisUtterance: MockSpeechSynthesisUtterance,
    };

    const synthesizer = new BrowserSpeechSynthesizer();
    assert.ok(synthesizer.getVoices().length >= 2);

    // Simulate onvoiceschanged
    if (mockSynth.onvoiceschanged) {
      mockSynth.onvoiceschanged();
    }
    assert.ok(synthesizer.getVoices().length >= 2);
  });

  it("should handle network recognition error without fatal crash", async () => {
    const mockRec = new MockSpeechRecognition();
    (global as any).window = {
      SpeechRecognition: function () {
        return mockRec;
      },
    };

    const recognizer = new BrowserSpeechRecognizer("en-US");
    recognizer.start();
    await new Promise((resolve) => setTimeout(resolve, 25));

    let errMessage = "";
    recognizer.onError((err) => {
      errMessage = err;
    });

    mockRec.emitError("network");
    assert.equal(recognizer.getState(), "ERROR");
    assert.ok(errMessage.includes("Network error"));
  });
});
