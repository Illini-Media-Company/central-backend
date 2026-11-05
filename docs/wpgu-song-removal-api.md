# WPGU Song Removal API

The song-removal frontends use the Central Backend's existing Google login,
Flask session cookie, and SeaSurf CSRF protection. Requests are same-origin;
there is no CORS contract. All endpoints require login.

Base path: `/wpgu-song-removal-requests/api`

For `POST` requests, send JSON with `Content-Type: application/json` and the
page's CSRF token in `X-CSRFToken`. Errors use this shape:

```json
{"error": "Human-readable message.", "code": "stable_error_code"}
```

## Form endpoints

### `GET /options`

Returns reason/status values, display labels, and field length limits. Use this
response to populate selects rather than duplicating labels in a frontend.

### `POST /reports`

```json
{
  "song_name": "Song title",
  "artist_name": "Artist",
  "song_version": "Clean edit",
  "reason": "audio_defect",
  "details": "Audio cuts out near the end."
}
```

`song_version` and `details` are optional, except `details` is required when
`reason` is `other`. Submitter identity is always taken from the logged-in user;
identity fields in the JSON are ignored. A successful request returns `201`
even if Slack is unavailable, with notification booleans in the response.

## Reviewer endpoints

These require membership in `wpgu-staff-operations`, `wpgu-directors`, or
`imc-staff-webdev`.

### `GET /reports`

Optional query parameters:

- `status`: `pending`, `in_progress`, `actioned`, or `no_action`
- `reason`: one of the values returned by `/options`
- `q`: case-insensitive search of song, artist, version, and details

The response contains song groups ordered by their newest matching report:

```json
{
  "groups": [
    {
      "song_key": "song|artist|clean edit",
      "song_name": "Song",
      "artist_name": "Artist",
      "song_version": "Clean edit",
      "report_count": 3,
      "matching_report_count": 1,
      "reports": []
    }
  ],
  "total_groups": 1,
  "matching_report_count": 1,
  "total_report_count": 3,
  "filters": {"status": "pending", "reason": null, "q": null}
}
```

`report_count` includes every report in the song group; the matching count and
nested reports reflect the active filters. Each report includes
`available_actions`, which can contain `claim`, `take_over`, `resolve`, or
`retry_slack` for the logged-in reviewer.

### `GET /reports/<uid>`

Returns one serialized report.

### `POST /reports/<uid>/claim`

Claims a pending report. No body is required.

### `POST /reports/<uid>/take-over`

Transfers an in-progress report to the logged-in reviewer. No body is required.

### `POST /reports/<uid>/resolve`

Only the current reviewer may resolve a report.

```json
{
  "status": "actioned",
  "resolution_notes": "Removed the incorrect file and replaced it with the clean edit."
}
```

`status` must be `actioned` or `no_action`, and notes are required. Resolved
reports are final in v1. Repeating the identical successful resolution is
idempotent and does not send another notification.

### `POST /reports/<uid>/retry-slack`

Updates the saved Slack message, posts it if one does not exist, or re-posts it
when Slack reports that the saved message is missing.

## Status and error behavior

- `400`: invalid JSON, field, filter, reason, status, or length
- `401`: no authenticated Central Backend session
- `403`: missing reviewer group or claimant ownership
- `404`: report does not exist
- `409`: invalid or conflicting status transition
- `502`: report remains saved, but an explicit Slack retry failed

Dates are ISO-8601 UTC strings and report IDs are integers. There is no delete,
reopen, automatic song-removal, or music-library endpoint.
