# Using Everything Agent

## Talking to Reachy

Just talk. There's no wake word and no button.

- Reachy starts listening as soon as it hears speech, and treats a short pause (about half a
  second) as the end of your turn. After "and", "um" or a trailing comma it waits longer, so a
  pause mid-thought isn't cut off.
- If you carry on before Reachy has started answering, it drops that answer and replies to
  everything you said together.
- Reachy starts speaking after the first sentence of its reply, usually 2 to 3 seconds after
  you stop. Its head moves while it speaks.
- Anything you say while it's still replying is answered once it has finished.

### Interrupting

Under **Settings → Listening**, switch on **Stop talking when I interrupt**. Reachy then turns
its voice down when you talk over it, and stops if you keep talking. It's off by default because
in a noisy room Reachy can mistake its own voice for yours.

### Languages

By default Reachy replies in the language you speak and switches when you do: English, Hindi,
French, Spanish and Japanese. To always use one language, choose it under
**Settings → How Reachy talks → Language**.

## The Home screen

| Part | What it shows |
| --- | --- |
| Reachy in 3D | The robot's real pose, live. The glow under it changes colour with what Reachy is doing. |
| Status | **Ready**, **Listening**, **Thinking**, **Speaking** or **Asleep** |
| Caption | What Reachy is saying, sentence by sentence as it says it |
| You said | The last thing Reachy heard from you |
| Speaker button | Mutes Reachy's voice |
| Microphone button | Stops Reachy hearing you |
| Put to sleep / Wake up | Sleep lowers Reachy's head, stops listening and closes the speech-to-text connection |

**Conversation** (top right) opens the transcript. From there you can type to Reachy instead of
talking, and **Start over** clears the conversation. The conversation is saved on the device, so
it survives restarts; Reachy keeps the last 60 messages.

## Settings

| Section | What you can change |
| --- | --- |
| How Reachy talks | Language, voice (browse Cartesia's library, hear a sample, then **Use**), and personality |
| Listening | How noisy your room is (microphone sensitivity), and interrupting |
| Microphone and speaker | Which microphone and speaker to use without the robot (desktop app only) |
| Advanced | Keys and AI model, Claude, a check that everything works, the web page PIN, start at login, and logs |

Changes take effect straight away. Saving keys restarts the conversation, and choosing a new
microphone or speaker restarts the app.

### Check that everything works

**Settings → Advanced → Check again** tests each part and says what's wrong:

| Check | Passes when |
| --- | --- |
| Hearing and speaking | The Cartesia key works |
| Thinking | The AI model provider accepts the key |
| Robot | The Reachy Mini software is running, with or without a robot |
| Microphone | Sound is arriving from the microphone |
| Hard questions | Claude is set up, or switched off |

## Hard questions go to Claude

With an Anthropic API key or a Claude setup token added under **Settings → Advanced → Claude for
hard questions**, Reachy hands questions that need the web or careful reasoning to Claude. Reachy
says it's looking into it, and Claude's answer is spoken as it arrives; you can keep talking
meanwhile.

|  | Anthropic API key | Claude setup token |
| --- | --- | --- |
| Get it | [platform.claude.com](https://platform.claude.com/settings/keys) | Run `claude setup-token` on any computer with Claude Code |
| Paid by | Per question, on your API account | Your Claude plan |
| Answer starts | Under a second, a few seconds with a web search | About a second, 8 to 10 seconds with a web search |

With both added, **Ask Claude with** chooses which one goes first; if it fails before saying
anything, Reachy tries the other. Claude can only search the web: it can't read files, run
anything, or see the app's other keys.

The setup token uses your own Claude plan, so it's for your own robot. Use an API key for
anything you set up for other people.

## Opening the app from another device

The app is also a web page, so a phone or laptop on the same network can open it:

- **On the robot:** <http://reachy-mini.local:8042>
- **Desktop app:** set a PIN under **Settings → Advanced → Web page PIN** and restart the app. The
  same section then shows the address to open.

Every device signs in with the PIN. See [Security](SECURITY.md) for how the page is protected.

## Desktop app extras

- **Tray icon:** open Reachy, mute the microphone or speaker, restart Reachy, switch start at
  login, or quit. The dot's colour shows whether Reachy is running (green), needs attention
  (amber) or has a problem (red).
- **Mute shortcut:** **Ctrl+Alt+M** on Windows, **Cmd+Alt+M** on macOS, from any app.
- **Closing the window** quits the app and puts the robot to sleep. Reachy also goes to sleep
  when you log off or shut down.
