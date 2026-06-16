# UI Contract: Topbar Utility Actions

## Stable Selectors

| Selector | Element | Expected behavior |
|----------|---------|-------------------|
| `[data-testid="topbar-help-button"]` | Help control | Navigates to `/help` |
| `[data-testid="topbar-notifications-button"]` | Notification bell | Toggles notification panel and exposes expanded state |
| `[data-testid="topbar-notifications-panel"]` | Notification panel | Visible only when notifications are open |
| `[data-testid="topbar-notifications-settings"]` | Notification settings action | Navigates to `/settings?tab=notifications` and closes panel |
| `[data-testid="topbar-user-menu-button"]` | Avatar menu button | Toggles user menu and closes notifications |
| `[data-testid="topbar-user-menu"]` | User menu | Visible only when avatar menu is open |
| `[data-testid="topbar-menu-profile"]` | Profile menu item | Navigates to `/profile` |
| `[data-testid="topbar-menu-settings"]` | Account settings menu item | Navigates to `/settings?tab=profile` |
| `[data-testid="topbar-menu-subscription"]` | Upgrade menu item | Navigates to `/settings?tab=subscription` |
| `[data-testid="topbar-menu-export"]` | Data export menu item | Navigates to `/settings?tab=export` |
| `[data-testid="settings-nav-{tab}"]` | Settings tab button | Activates tab and updates `?tab={tab}` |
| `[data-testid="settings-panel-{tab}"]` | Settings tab panel wrapper | Visible for active tab |

## Interaction Rules

- The Help button must not open a panel; it navigates directly.
- The Notification button must set `aria-expanded` according to panel visibility.
- The Avatar menu button must set `aria-expanded` according to menu visibility.
- Opening one topbar popover closes the other.
- Escape closes the notification panel when it is open.
- Unsupported Settings tab query values render the profile panel.

## E2E Coverage

- Help navigation from dashboard.
- Notification panel open, outside/Escape close, and settings link navigation.
- Avatar menu navigation to profile, profile settings, subscription settings, and export settings.
- Settings direct load for supported and unsupported tab query values.
