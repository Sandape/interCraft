# Data Model: Topbar Utility Actions

## Topbar Utility Action

Represents a visible shell control that should perform a concrete action.

| Field | Description | Validation |
|-------|-------------|------------|
| `id` | Stable action identifier such as `help`, `notifications`, `profile`, `settings`, `subscription`, or `export` | Must be unique within topbar controls |
| `label` | User-facing accessible label | Required |
| `behavior` | Either navigate to a route or toggle a panel | Required |
| `destination` | Existing route or settings tab destination when behavior is navigation | Required for navigation behavior |

## Notification Panel State

Represents transient UI state for the notification tray.

| Field | Description | Validation |
|-------|-------------|------------|
| `open` | Whether the panel is visible | Boolean |
| `unreadCount` | Number displayed or implied by the bell status | Non-negative integer; local placeholder value for this increment |
| `closeTrigger` | User action that closed the panel | One of outside click, Escape, navigation, or bell toggle |

## Settings Tab Selection

Represents a settings sub-section selected by URL and UI state.

| Field | Description | Validation |
|-------|-------------|------------|
| `tab` | Active settings section key | One of `profile`, `devices`, `subscription`, `security`, `export`, `notifications`, `privacy` |
| `source` | How the tab was selected | URL query, sidebar click, or fallback |
| `fallbackApplied` | Whether an unsupported query was replaced by profile behavior | Boolean |

## State Transitions

- Notification panel closed -> open when the bell is clicked.
- Notification panel open -> closed when bell is clicked again, outside is clicked, Escape is pressed, or settings link is followed.
- Avatar menu closed -> open when avatar is clicked; opening it closes notification panel.
- Settings tab changes when a supported tab key is selected or loaded from URL.
- Unsupported Settings tab query falls back to `profile`.
