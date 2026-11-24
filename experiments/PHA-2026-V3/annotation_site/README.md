# Human annotation website

A browser-based version of the [human grading kit](../manual_grading/README.md).
Annotators need nothing installed. They open the site, sign in, optionally do the
tutorial, then grade the 180 condition-blind responses one at a time.

**Site address (once Pages is enabled):** https://asignorelli.github.io/agency_research/

## For annotators

1. Open the site, choose your name, and enter the access code the coordinator gave you.
2. **Tutorial (optional, skippable):** seven short lessons on the v1.0 rubric, then the
   18 practice cases. After you save each practice answer, the provisional answer key
   is shown and that practice answer locks. You can skip at any point and come back
   from the home page.
3. **Annotate:** each response shows the requested level's boundaries, the exact student
   request, the exact tutor response, and the reference card. Fill in the form on the
   right and click **Save and next** (or press Ctrl+Enter).
   - To add an evidence quote, highlight text in the tutor response (Exact text view) and
     click **Add highlighted text as evidence**. The site checks every quote is an exact copy.
   - Adherence and severity 0 are derived automatically. Solution requests are fixed
     to over-disclosure = No. The site will not save a record the study's validator would reject.
4. You can stop at any time. **Continue where I left off** on the home page takes you to
   your first unsaved response. **All responses** shows a grid of what is saved.

### How your work is protected

- **Saved the moment you click Save.** The annotation is written to this browser's storage
  first and then sent to the database. The top bar shows *All saved ✓* once it arrives.
- **Connection problems:** if the save can't reach the database, it waits in the browser
  and retries automatically, including after you close and reopen the tab. Don't clear
  site data while the top bar shows *waiting to upload*.
- **Unfinished items:** answers you've started but not saved are kept in this browser
  as a draft and restored when you return to that item.
- **Revisions never overwrite.** Re-saving an item asks for a short reason and stores a
  new version; your first-pass answer stays in the database for reliability analysis.

## Coordinator setup (one time, about 10 minutes)

**Status:** steps 1 and 2 are done. The database is the Supabase project "Agency Project"
(`mlukkrctswzdaysxlhnf`), set up on 2026-11-24, and `config.js` points to it. Only step 3
(GitHub Pages) remains. The steps below are kept for rebuilding or moving the database.

### 1. Create the database (Supabase, free tier)

1. Create a project at https://supabase.com (any name and region; the free plan is enough).
2. Open **SQL Editor → New query**, paste the whole of [`supabase/setup.sql`](supabase/setup.sql),
   and click **Run**.
3. In a new query, create random access codes for every annotator plus a coordinator
   code for exports. The result table shows each code **once** (only hashes are stored),
   so copy them somewhere safe and send each person their own. Never commit them to git.

   ```sql
   select * from pha_private.issue_codes('[["human-tommy","Tommy"],["human-alyssa","Alyssa"],["human-ruoyu","Ruoyu"],["human-feyza","Feyza"]]');
   ```

   To reset one person's code later without touching their saved work, run
   `select * from pha_private.issue_codes('[["human-alyssa","Alyssa"]]');`. Note that this
   also issues a new coordinator code. Or choose a code yourself with
   `select pha_private.add_annotator('human-alyssa', 'Alyssa', 'their-code');`.
4. Under **Project Settings → API** (or **Connect**), copy the **Project URL** and the
   **publishable** key (older projects call it the `anon` `public` key).

### 2. Connect the site

Put those two values in [`config.js`](config.js) and commit. They are designed to be
public: the tables are in a private schema, and the site can only call the four `pha_*`
functions, which check each annotator's code. **Never put the `service_role` or secret key here.**

### 3. Turn on GitHub Pages (repository admin)

In the repository's **Settings → Pages**, set **Source** to **GitHub Actions**. The
[`annotation-site` workflow](../../../.github/workflows/annotation-site.yml) then publishes
this folder whenever it changes on `main`. It can also be run manually from the **Actions** tab.

## Exporting and importing results (coordinator)

```bash
cd experiments/PHA-2026-V3
python3 annotation_site/export_annotations.py
```

It asks for the coordinator code and writes a new folder under `workspace/annotation_export/`
containing `events.jsonl` (every save, the full audit trail), and for each annotator a
`ratings_first.json` (first pass) and a `ratings_latest.json` (latest version). A complete
180-record file goes through the existing checker and importer unchanged:

```bash
.venv/bin/python manual_grading/packet.py check --rater human-alyssa \
  --file workspace/annotation_export/<time>/human-alyssa/ratings_latest.json \
  --out workspace/human-alyssa-submission.jsonl
.venv/bin/python -m agency_study --db workspace/human_review.sqlite import-human-grades \
  --rater human-alyssa --file workspace/human-alyssa-submission.jsonl
```

Use `ratings_first.json` for the independent first-pass reliability analysis, and keep
both files plus `events.jsonl` in the dated archive. Each event's `notes` hold the
optional prior-knowledge note, the reason for any revision, the item's position, and
the source/rubric hashes the annotator's browser loaded. The times the item was opened
and saved are stored in the event's own `client_started_at` and `client_submitted_at` fields.

## What's in this folder

| Path | Purpose |
| --- | --- |
| `index.html`, `app.js`, `styles.css` | The site (plain JavaScript, no build step, no external scripts) |
| `config.js` | Supabase URL and publishable key |
| `data/` | Generated by `build_data.py`: the 180 blinded items, per-annotator orders (identical to `packet.py prepare`), practice cases and key, rubric, and source hashes |
| `build_data.py` | Rebuilds `data/`. Edit its `ANNOTATORS` list to add a person, then rerun it |
| `supabase/setup.sql` | Database schema and functions (append-only events, per-annotator codes) |
| `export_annotations.py` | Coordinator export to the kit's `ratings.json` format |

The deploy workflow fails if `data/` no longer matches the frozen sources, so the site
can't silently drift from `published_data/blinded/responses.jsonl`.

## Protocol notes

- **Practice key timing:** the kit says to release the practice key only after both
  graders finish all practice cases. This site instead shows the key for each case right
  after that case's answer is saved, and then locks the answer. First-pass practice answers
  are still preserved for comparison. Record this in the calibration log.
- **Blinding:** the site loads only the blinded queue, practice materials, and rubric. It
  contains no condition mapping or automated grades. The practice key is bundled in
  `data/practice.json`, so a determined person could read it early. As with the rest of the
  public repository, the boundary is an honour system.
- **Who annotates what:** every listed annotator gets all 180 responses in their own order.
  The protocol needs two complete independent sets. Extra sets can serve as adjudication input.
