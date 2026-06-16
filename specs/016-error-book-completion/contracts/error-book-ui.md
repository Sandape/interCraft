# Error Book UI Contract

Route: `/error-book`

## Required Visible States

- Page title: `错题本`
- Primary action: `添加错题`
- Empty state: shown when no questions are available under current filters
- Loading state: shown while server data loads
- Error state: shown when list or mutation requests fail
- Detail state: shown when a question is selected
- No-results state: shown when search/filter removes all loaded questions

## Primary Workflow

1. User opens `/error-book`.
2. User clicks `添加错题`.
3. Modal opens with required question field, optional answer field, and optional dimension select.
4. User saves a valid question.
5. Modal closes, list refreshes, created question is visible.
6. User selects the question.
7. Detail panel shows status, frequency, question, answer, dimension, score, and actions.

## Review Workflow

Available actions depend on status/frequency:

| Condition | Required Action |
|-----------|-----------------|
| `frequency > 0` | `答对一次` |
| `frequency > 0` | `开始强化` |
| `status=mastered` | `重置为未掌握` |
| any non-deleted question | `删除` |

After `答对一次`, the visible status and frequency update without a full page reload.

## Error Behavior

- Create validation errors stay in the modal and do not clear user input.
- Recall/reset/delete errors show an alert region on the page or detail panel.
- Deleted selected question clears the detail panel.
- Navigation away and back reloads server state and keeps the UI usable.

## Accessibility & Layout

- All icon-only controls must have accessible labels.
- Modal inputs must have labels.
- Interactive elements must be keyboard focusable.
- Text must not overlap in desktop or mobile widths.
