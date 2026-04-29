# Create Note by Calendar Event

Obsidian plugin that fetches events from a CalDAV calendar and creates notes from a customizable template.

## How it works

1. Connects to your CalDAV server using URL, username and password
2. Opens a sidebar panel (**Event View**) with a list of events for the selected date
3. Click any event to instantly create a note in your vault, populated with event data using a template

## Features

- **Event View** — sidebar panel showing calendar events with date navigation (previous / next day)
- **Template-based notes** — use your own Obsidian note as a template with placeholders
- **CalDAV support** — works with any CalDAV-compatible calendar (Nextcloud, Google Calendar via CalDAV, etc.)
- **Auto-generated notes** — notes are named after the event title and opened automatically

## Template placeholders

In your template note, use the following placeholders:

| Placeholder | Value |
|---|---|
| `{event_title}` | Event title |
| `{event_date}` | Start date and time |
| `{event_org}` | Organizer name |
| `{event_participants}` | Required participants |
| `{event_optional_participants}` | Optional participants |
| `{event_location}` | Event location |
| `{event_link}` | Event URL |
| `{event_description}` | Event description |

Example template:

```markdown
# {event_title}

**Date:** {event_date}
**Organizer:** {event_org}
**Location:** {event_location}
**Participants:** {event_participants}

## Description
{event_description}
```

## Settings

| Setting | Description |
|---|---|
| **URL** | CalDAV calendar URL |
| **Text field** | Username (login) |
| **Password field** | Password |
| **File path** | Path to template note (without `.md` extension) |
| **Folder path** | Folder where notes will be created |

## Installation

### Manual

1. Download `main.js`, `styles.css`, and `manifest.json` from the [latest release](https://github.com/Nick-Senin/obsidian-create-note-by-calendar-event/releases)
2. Copy them into your vault: `.obsidian/plugins/calendar-create-note-by-event/`
3. Enable the plugin in Obsidian Settings → Community Plugins

### From source

```bash
git clone https://github.com/Nick-Senin/obsidian-create-note-by-calendar-event.git
cd obsidian-create-note-by-calendar-event
npm install
npm run build
```

Then copy the built files to `.obsidian/plugins/calendar-create-note-by-event/`.

## Development

- `npm run dev` — compile in watch mode
- `npm run build` — production build
- Requires Node.js v16+
