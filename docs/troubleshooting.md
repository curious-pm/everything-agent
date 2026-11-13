# Troubleshooting

Start with **Settings → Advanced → Check again**. It tests the keys, the AI model, the robot and
the microphone, and says what's wrong.

## Finding the logs

- **Desktop app:** **Settings → Advanced → Show logs folder**.
- **Robot or browser:** **Settings → Advanced → Show logs**, then pick **Reachy**, **Robot** or
  **Desktop app**, and **Copy** to paste them into an issue.
- **On disk:** see [Configuration](configuration.md#where-settings-are-stored). `app.log` is the
  conversation, `daemon.log` the Reachy Mini software, `desktop.log` the desktop app's core.

When you report a problem, include the relevant part of `app.log`, and check it for anything
private before you post it.

## The desktop app

**"Another Reachy app is using my body."**
Reachy Mini Control, or another app, is already running the robot software. Quit it; Everything
Agent starts by itself once it's gone. If the message underneath says another copy of Everything
Agent is running, quit that copy from its tray icon, then start this one again.

**"I can't find my robot body."**
The robot didn't answer. Check it's plugged in over USB and switched on. To use the computer's
microphone and speaker instead, unplug it, or set `REACHY_MODE=mockup`.

**Windows says "Windows protected your PC", or macOS won't open the app.**
The installers aren't code-signed yet. On Windows choose **More info → Run anyway**; on macOS
right-click the app and choose **Open** the first time.

## Hearing and speaking

**Reachy doesn't hear me.**
- Check the microphone button on the Home screen isn't off, and the tray's **Mute Reachy's
  microphone** isn't ticked (the desktop shortcut is Ctrl+Alt+M, or Cmd+Alt+M on macOS).
- Without the robot, check the microphone under **Settings → Microphone and speaker**.
- In a quiet room, set **Settings → Listening → My room is** to **Very quiet room**.

**Reachy reacts to background noise.**
Set **My room is** to **Noisy room**.

**Reachy stops talking by itself.**
It can mistake its own voice for yours when interrupting is on. Switch off **Settings →
Listening → Stop talking when I interrupt**, or use it in a quieter room.

**Reachy can't be heard.**
Check the speaker button on the Home screen and the system volume. Without the robot, check the
speaker under **Settings → Microphone and speaker**.

**Replies take a long time to start.**
Most of the wait is the AI model. Each reply's timing is in `app.log` as a `Timing:` line. A
faster model or a provider closer to you helps; see [Configuration](configuration.md#ai-model).

## Keys and Claude

**"The AI model didn't answer."**
The key, model name or address is wrong, or the provider is down. **Check again** shows which.

**Reachy says it couldn't get an answer from Claude.**
It says why: a rejected key or token, a usage limit, or a timeout. Check the key under
**Settings → Advanced → Claude for hard questions**. With both a key and a setup token, Reachy
tries the other one automatically.

## The web page

**I forgot the PIN.**
Delete the `WEB_PIN_HASH` line from the settings file and restart the app; the next visit sets a
new PIN. See [Configuration](configuration.md#where-settings-are-stored) for where the file is.

**"Too many wrong PINs."**
After five wrong PINs a device has to wait five minutes, and after 30 wrong PINs in an hour every
device does.

**My phone can't open the desktop app's page.**
Set a PIN under **Settings → Advanced → Web page PIN**, then restart the app. Until a PIN is set,
the page only answers on the computer itself.

**"This page isn't served under that name."**
The page refuses host names it doesn't know. Add the name to `WEB_ALLOWED_HOSTS`, or use the IP
address.

**The page doesn't open at all.**
Another program may be using port 8042. Set `WEB_PORT` to a free port and restart.

## Still stuck?

[Open an issue](https://github.com/curious-pm/everything-agent/issues) with what you did, what
happened, your system, and the relevant part of `app.log`. Report security problems privately
instead; see [Security](SECURITY.md).
