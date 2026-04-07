# Skill: Telegram Notify

Use this skill to send Telegram messages via the MyCow bridge.

## How to use it

The MyCow Telegram bridge is already active when the daemon is running. To send a message from inside an agent, write the message text as output — the "cron" and "heartbeat" triggers automatically send the output to Telegram if `telegram_without_approval: true` is set in cron.yaml.

## Message formatting

Telegram supports a Markdown subset:
```
*bold text*
_italic text_
`inline code`
[link text](https://url)
```

## Recommended message structure

```
*[AgentName] Short title*

- Point 1
- Point 2
- Point 3

Source: [link](https://url)
```

## Limits

- Maximum 4096 characters per message
- Do not use HTML — use Markdown
- For long lists, split into multiple messages
- Do not send messages if you have no new information to share

## When NOT to send

- If the heartbeat found nothing relevant → do not send
- If the task failed with a technical error → the daemon notifies automatically
- Do not send "no news" messages — only useful information
