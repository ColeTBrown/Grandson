// Talks to Claude with the official Anthropic SDK.
import Anthropic from "@anthropic-ai/sdk";
import { MODEL, SYSTEM_PROMPT } from "./prompts.js";

/** An error whose message is already written for the person (plain language). */
export class FriendlyError extends Error {
  constructor(message, { needsSetup = false } = {}) {
    super(message);
    this.needsSetup = needsSetup;
  }
}

export function makeClient(apiKey) {
  return new Anthropic({
    apiKey,
    // This is the person's own key, kept in this browser's extension storage
    // and used only from extension pages. Web pages cannot read it.
    dangerouslyAllowBrowser: true,
    maxRetries: 2,
  });
}

function friendly(err) {
  if (err instanceof FriendlyError) return err;
  if (err instanceof Anthropic.AuthenticationError || err instanceof Anthropic.PermissionDeniedError) {
    return new FriendlyError(
      "The key that lets me think isn't working. Please open Settings and check it, or ask a family member to help.",
      { needsSetup: true },
    );
  }
  if (err instanceof Anthropic.RateLimitError) {
    return new FriendlyError("I'm being asked too much right now. Let's wait a minute and try again.");
  }
  if (err instanceof Anthropic.APIConnectionError) {
    return new FriendlyError(
      "I couldn't reach my brain just now. This is usually the internet connection. Let's try again in a moment.",
    );
  }
  if (err instanceof Anthropic.APIError && err.status === 400 && /credit|billing/i.test(err.message || "")) {
    return new FriendlyError(
      "The account that pays for my thinking has run out of credit. Please ask the family member who set me up to top it up.",
      { needsSetup: true },
    );
  }
  if (err instanceof Anthropic.APIError && err.status >= 500) {
    return new FriendlyError("My brain is having a hiccup on its end. Let's try again in a moment.");
  }
  if (err?.name === "AbortError" || err instanceof Anthropic.APIUserAbortError) {
    return new FriendlyError("Stopped.");
  }
  console.error("Grandson: unexpected error", err);
  return new FriendlyError("Something went wrong and I couldn't answer. Let's try that again.");
}

/**
 * Ask Claude and stream the answer.
 * `messages` is the whole conversation so far. Returns the content blocks of
 * the reply, to be appended to the conversation unchanged for follow-ups.
 */
export async function ask({ client, messages, onText, signal }) {
  try {
    const stream = client.beta.messages.stream(
      {
        model: MODEL,
        max_tokens: 8000,
        system: SYSTEM_PROMPT,
        // Short, friendly explanations: quick answers matter more than depth.
        output_config: { effort: "low" },
        // If the model declines a request, let the API retry on a fallback
        // model so the person still gets an answer.
        betas: ["server-side-fallback-2026-07-01"],
        fallbacks: "default",
        messages,
      },
      { signal },
    );
    stream.on("text", (delta) => onText(delta));
    const message = await stream.finalMessage();

    if (message.stop_reason === "refusal") {
      throw new FriendlyError(
        "I'm not able to help with this page. If something here worries you, close the page and check with a family member.",
      );
    }
    const hasText = message.content.some((b) => b.type === "text" && b.text.trim());
    if (!hasText) {
      throw new FriendlyError("I looked, but couldn't find the words to describe it. Let's try that again.");
    }
    return message.content;
  } catch (err) {
    throw friendly(err);
  }
}

/** Check a key works, without spending anything. Throws FriendlyError if not. */
export async function checkKey(apiKey) {
  try {
    await makeClient(apiKey).models.retrieve(MODEL);
  } catch (err) {
    throw friendly(err);
  }
}
