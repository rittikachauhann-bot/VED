# VED dashboard

`index.html` is the page of a Claude "Data" (dashboard) artifact. It reads one dataset, `tracker`,
an attached CSV that the daily VED run re-uploads, and works out the rest with `dash.calc`:

| Calc | What it gives |
|---|---|
| `summary` | Roles tracked, strong matches (score ≥ 70), CV ready, applied, interviews, offers |
| `by_status` | Roles per pipeline stage, in stage order |
| `by_company` | Roles per company, split into strong matches and the rest |

## CSV schema (`job_tracker.csv`)

Columns, in this order:

`score,status,company,title,location,sponsorship,pay_range,job_url,date_found,cv_url,coverage,applied_on,follow_up_due,notes`

- `title` plain text, `job_url` and `cv_url` bare URLs, `coverage` a decimal (0.8 = 80%), dates `YYYY-MM-DD`.
- `job_url` must be unique: it is the table's row key.
- Status values: Maybe, Shortlisted, CV ready, Approved to apply, Applied, Outreach sent, Interview,
  Offer, Rejected, Skipped, Withdrawn.

`sample_job_tracker.csv` holds made-up example rows only.
