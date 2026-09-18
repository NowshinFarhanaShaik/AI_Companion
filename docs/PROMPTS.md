# Development Prompts

This project was built with Claude Code. The work started with a design conversation, which produced a written spec and an implementation plan (`docs/superpowers/`). The plan was then executed one phase at a time, with a review after each phase. The prompts below are the ones that materially shaped the work, copied as written and grouped by area.

## Architecture

- "hey can you have understanding on this file please '.../Project_Requirements.pdf'...let me know your understaning on it"
- "is there any techstack mentioned in that task?"
- "is this techstack better? python,django,react,html,css,js,node"
- "okay give me the tech stack used for this..final one.."
- "okay now lets plan to implement that task"
- Deadline and constraints, given as answers to the assistant's questions: "lets complete this by tommorrow...with proper plan and architecture"; AI access: "Google Gemini key (free tier)"; hosting: "can you suggest me best one but free"
- "i think first we better start plan on implementation once we done with prototype then we can go for deployment right?"
- "okay lets plan to implement carefully..since it is task right...we need to plan for both frontend and backend as well"
- "approved, write the spec and implementation plan"

## Backend

- "create venv and install al those i that" (the environment already existed; the assistant verified it)

- "can you verify it and once ok..lets start implementation but you should maintain code quality...dont write unnecessary functions..and comments as well...maintain proper folder structure ...if you need any skills you can use"
- "implement phase by phase"

## Frontend

Covered by the two Backend prompts above; Phase 1 built the API and the React shell together.

## Database

No separate prompts. The data model came from the design conversation (spec section 4).

## AI

- "yeah i have updated go on" (after adding the Gemini key; started Phase 2: AI module, job queue, document pipeline)
- "phase 3...dont use free quota please" (Tutor phase; built and verified entirely with the fake provider and seeded data, with no real API calls)
- "continue" / "continue now" (Phase 4, adaptive quiz)
- "do with your recommendations since you have great context of this right" (answer when asked whether the owner or the assistant should write `compute_priority`; the assistant wrote it from spec §7.1)
- "continue with phase 5" (mastery, growth, recommendations and dashboards)
- "okay go with next phase" (Phase 6: analytics and the Admin dashboard)
- "go with phase 7" (evaluation suite, rate limits, error handling, seed data and frontend tests; the eval harness was checked offline with a scripted fake provider, and no real eval run was made without the owner's approval)

Before writing the Gemini provider, the assistant ran a short probe script against the live API. The probe, not a prompt, is what found that function responses must use `role="user"` and that the model's raw turn must be replayed.

## Debugging

No prompts yet.

## Testing

No separate prompts. The plan requires a failing test before each implementation, and a browser check at the end of each phase. Phase 7 added `manage.py run_evals` (AI quality) and Vitest (`npm test`) for the frontend.

## Documentation

No prompts yet.
