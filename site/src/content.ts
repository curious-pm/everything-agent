export const REPO = "https://github.com/curious-pm/Everything-Agent";
export const RELEASES = `${REPO}/releases`;
export const LATEST_RELEASE_API = "https://api.github.com/repos/curious-pm/Everything-Agent/releases/latest";

export type Phase = "listening" | "thinking" | "speaking";

export type Beat =
  | { kind: "hear"; text: string; pause: number }
  | { kind: "think"; pause: number }
  | { kind: "say"; text: string; stopAfterWords?: number }
  | { kind: "rest"; pause: number };

export const conversation: Beat[] = [
  { kind: "rest", pause: 500 },
  { kind: "hear", text: "Hey Reachy, what can you do?", pause: 900 },
  { kind: "think", pause: 1100 },
  { kind: "say", text: "I can chat with you, answer your questions, and look things up for you, in", stopAfterWords: 9 },
  { kind: "hear", text: "Wait, en español?", pause: 1100 },
  { kind: "think", pause: 1000 },
  { kind: "say", text: "¡Claro! Puedo charlar contigo, responder tus preguntas y buscar cosas por ti." },
  { kind: "rest", pause: 600 },
];

export type Question = { ask: string; reply: string; think: number };

export const questions: Question[] = [
  {
    ask: "What can you do?",
    reply: "I can chat with you, answer your questions, and look things up when something needs the web.",
    think: 1100,
  },
  {
    ask: "¿Hablas español?",
    reply: "¡Claro! Puedo hablar contigo en español, o en el idioma que prefieras.",
    think: 1000,
  },
  {
    ask: "Tell me a fun fact",
    reply: "Octopuses have three hearts. Two pump blood through the gills, and one sends it round the rest of the body.",
    think: 1300,
  },
];

export function beatsFor(question: Question): Beat[] {
  return [
    { kind: "hear", text: question.ask, pause: 700 },
    { kind: "think", pause: question.think },
    { kind: "say", text: question.reply },
  ];
}

export const conversationSummary =
  "You: Hey Reachy, what can you do? Reachy starts answering; you cut in to ask for Spanish, " +
  "and Reachy stops and replies: ¡Claro! Puedo charlar contigo, responder tus preguntas y buscar cosas por ti.";

export const timeline = [
  {
    phase: "listening" as Phase,
    when: "0 s",
    title: "You stop talking",
    body: "Reachy waits for 550 ms of silence, longer after “and”, “um” or a trailing comma, so a pause isn't cut off.",
  },
  {
    phase: "thinking" as Phase,
    when: "~1 s",
    title: "It thinks",
    body: "Your words, already transcribed while you spoke, go to the model. Gemini 2.5 Flash takes 1.3 to 2 seconds to begin.",
  },
  {
    phase: "speaking" as Phase,
    when: "2.5–3 s",
    title: "It answers",
    body: "The first finished sentence goes straight to the voice while the rest is still being written. Its head moves as it speaks.",
  },
];

export type Exchange = { title: string; you?: string; reachy?: string; more: string };

export const exchanges: Exchange[] = [
  {
    title: "Talk over it",
    you: "“Actually, never mind.”",
    more: "Reachy's voice drops, then stops if you keep talking. Its own voice never sets this off.",
  },
  {
    title: "Speak your language",
    you: "“Bonjour Reachy, ça va ?”",
    reachy: "Oui, très bien, merci !",
    more: "English, Hindi, French, Spanish and Japanese. Reachy replies in the one you use.",
  },
  {
    title: "Hand hard questions to Claude",
    you: "“What were the big headlines this morning?”",
    reachy: "Let me look into that.",
    more:
      "With an Anthropic key or a Claude setup token, questions that need the web go to Claude Haiku. " +
      "Its answer is spoken sentence by sentence as it arrives, and you can keep talking meanwhile.",
  },
  {
    title: "Use any model",
    more: "OpenRouter, any OpenAI-compatible provider, or a local model through Ollama. Pick Reachy's voice from Cartesia's library.",
  },
];

export const leaves = [
  {
    lead: "Your voice, only while you're talking.",
    rest: "A local loudness check opens the speech-to-text connection on your first word and closes it after a quiet minute.",
  },
  { lead: "Text, to the model you choose.", rest: "With Ollama, nothing leaves your network." },
  {
    lead: "Hard questions, to Claude,",
    rest: "if you add a key. Claude can only search the web: it can't read files or run anything, and never sees your other keys.",
  },
];

export const keys = [
  { what: "Hearing and speaking", service: "Cartesia", link: "https://play.cartesia.ai/keys", label: "play.cartesia.ai/keys" },
  { what: "Thinking", service: "OpenRouter, any OpenAI-compatible provider, or Ollama", link: "https://openrouter.ai/keys", label: "openrouter.ai/keys" },
  { what: "Hard questions (optional)", service: "Anthropic API key or Claude setup token", link: "https://platform.claude.com/settings/keys", label: "platform.claude.com" },
];
