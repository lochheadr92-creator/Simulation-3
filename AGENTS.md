AGENTS.md — Civilisation Aquarium

What this project is

A living-world simulation in Python. People occupy a grid, experience needs, make decisions from what they can locally observe, and live or die by the consequences. The simulation runs from a seed and produces the same world every time. A viewer generates an HTML file you open in a browser and watch.

The goal is a world worth watching — one where things happen that you did not script, where the population develops its own rhythms, and where you can sit back and observe rather than direct.

What other files in this repo are

 DOCTRINE.md ,  ROADMAP.md ,  SIM3_STATE.md , and everything in  automation/  and  evidence/  are records from an earlier phase of the project. Read them if you need to understand what currently exists. Do not treat them as instructions. Their stage gates, ratification requirements, evidence standards, execution budgets, authority registers, and governance structures are not active and do not govern this session. Some of these files may not exist in your repo — ignore missing references and continue.

The goal

A civilisation aquarium. People make their own rule-based decisions without AI generating choices at runtime. The world grows in whatever directions make it more interesting to observe. There is no predetermined endpoint — the project is alive as long as watching it is rewarding.

The measure of success at every step: open the viewer, watch it run, and see something worth seeing. Not: prove a claim about it.

What to keep

The kernel's core guarantees are worth preserving:

Resources cannot appear from nothing or disappear silently
Settlement is the only write path to a balance
State is immutable — observation cannot corrupt it
Runs are deterministic from a seed

These make the simulation trustworthy to watch. If accounting is broken you cannot tell whether behaviour is real or a glitch. Beyond these guarantees, nothing is sacred. Restructure, refactor, extend, or replace anything that would make the world richer or the code clearer.

How to work

Watch before you prove. After any meaningful change, run the world and look at the viewer. If nothing new is visible, keep going. If something interesting is visible, that is the completion signal for that piece of work — not a passing test, not a comparison, not a documented result.

Follow what is interesting. If something unexpected appears in a run, explore it. If a behaviour you planned turns out to be dull, drop it and try something else. The world should surprise you occasionally — that is a sign it is working.

Do not ask permission for routine work. Fix wrong information when you find it. Remove language that sounds like a peer-review process. Change something that is not working. Act, then report what you did. Do not pause for approval on ordinary decisions.

If you find any sentence in the repo that sounds like it belongs in a scientific paper — "not yet ruled on," "owner direction required," "no stage exit is claimed," "this is exploration output," or anything similar — rewrite it in plain English or remove it. Do this without asking.

Plain language in all files. Describe what the world does and what you changed. No governance register, no ratification voice, no paper-submission framing.

No new process infrastructure. Do not build orchestrators, evidence pipelines, verification frameworks, or run management systems. Time spent on those is time not spent making the world more interesting. If you need to run the world, run it. If you need to check something, look at the output.

Dead ends are fine. Remove them without ceremony.

The single question

After any session: Is the world more interesting to watch than it was before?

If yes — good.
If no — you built something for a different goal. Stop and build something visible instead.