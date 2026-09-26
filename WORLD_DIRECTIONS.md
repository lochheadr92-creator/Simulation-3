# Simulation 3 — Development Directions

This is the current working list of things to try. The order reflects our
present priorities and can change when watching the world reveals a better
direction. AGENTS.md remains the project brief. This document introduces no
approval requirements, stage gates, fixed run budgets or extra paperwork.

"Civilisation aquarium" describes the kind of world we are building. The
project is called Simulation 3.

## 1. What already exists

The foundation below was checked against the code as this was written.

**A deterministic grid world.** People occupy a 12x12 grid. Each tick every
living person observes what is near them, decides from that observation
alone, the kernel settles whatever moves resources, and world processes
apply movement, needs, death, renewal and births. The same seed always
produces the same world, and a saved run replays to the same result.

**Three needs.** Hunger, thirst and cold. Each rises on its own schedule and
kills at its own level. Cold falls again while a person is on their home
cell. When more than one need is calling, a person serves whichever will
kill them soonest at the rate it is rising.

**Food and water sources.** Two food sources and two wells at fixed places,
each renewing on its own cadence up to a cap. People walk to a source, claim
a pack of units, carry them, and eat or drink later. Claims are settled by
the kernel, so two people wanting the last unit cannot both have it.

**Rough ground and shelter spots.** Roughly a fifth of the grid is rough
ground, which costs an extra tick to cross. A few cells are shelter spots,
where hunger and thirst rise more slowly. Sources and homes are always open
ground. Terrain is drawn from its own generator, so changing a terrain
setting never moves anybody's home.

**People build shelters.** With no need calling and standing at home on bare
ground, a person works on a shelter. It takes several ticks of work, and
work already done is kept when a need calls them away, so shelters go up in
snatches between trips. A finished shelter is permanent and slows hunger and
thirst for whoever stands on it.

**People carry food to someone visibly starving.** Distress is visible: you
can see that somebody nearby is in a hunger or thirst emergency, though not
how bad it is. Someone with nothing of their own calling and a spare unit in
hand will walk to the nearest visibly starving person and hand over one
unit. The handover is a kernel transfer and can be refused.

**Births and a changing population.** When two people who have each finished
a shelter, and who are neither hungry nor thirsty nor cold, stand on
adjacent cells for a few ticks running, a new person arrives with a home on
the nearest free cell. They hold nothing: a birth creates no food and no
water. A run whose roster changes still seals, verifies and replays.

**Walking round rough ground.** A person heading anywhere picks their way
round the rough ground they can see, counting a rough cell as two ticks and
everything else as one, and counting whatever lies beyond their sight as open
in a straight line. Only the edge of sight is judged: measuring a cell in the
middle of what they can see would pretend the rough beyond it was not there,
and a cell just short of a wall would look like the best place on the map.
Going round one rough cell costs more than crossing it, so nobody bothers; a
run of three is worth avoiding, and that is the case this exists for.
`--routing off` restores straight-line walking.

It made a large difference. Over 400 ticks the time people spend bogged in
rough ground fell by about nine tenths — 321 stuck ticks to 17 on seed 7, 739
to 116 on seed 23 — and three seeds of four ended much better off, seed 7
going from 5 alive of 6 to 14 of 18 and seed 23 from 12 of 53 to 28 of 75.
Seed 11 went the other way, 24 of 62 down to 5 of 41: a more efficient world
breeds faster and can overshoot its food. The 50-person cost check still meets
every target.

**Asking for food, built but switched off.** `--requests on` gives a hungry
person holding nothing the ability to ask somebody they can see carrying food
for it. Asking is speech: they call out and walk on, so it costs no tick. The
person asked answers next tick, and agrees only if nothing of their own is
calling, they hold a unit, and they are not already carrying one for somebody
else. An agreement is held in the world state until the unit is handed over
or they lose sight of the asker, so an errand once taken on is not dropped
for a nearer stranger. The handover is a kernel transfer. The whole exchange
is in the viewer: who asked, who agreed, who went unanswered, who delivered.

It is off by default because it costs a growing world about half its people.
Over 400 ticks it took seed 11 from 24 alive of 62 down to 3 of 25, and seed
23 from 12 of 53 to 4 of 31. Six-person worlds that never grow are unaffected.
The reason is not the price of asking, which is nothing: it is that carrying
food to somebody takes the helper away from home for many ticks, and a birth
needs two well, sheltered neighbours standing adjacent. Helping and settling
down compete for the same time, and the handful of units delivered does not
pay for the children not had.

That looked at first like a brittle birth rule, so we tried making time
together decay by a tick when a pair separates instead of resetting to
nothing. It did not help — births still fell by more than half with asking on
— and it made the world worse without asking, taking seed 11 from 24 survivors
to 6, because pairs who were barely together at all accumulated enough credit
to breed. The change was dropped and the consecutive rule kept. The trade-off
is real, not an artefact.

**A map viewer.** `world/viewer.py` renders a saved run as a self-contained
HTML page: the grid with terrain, sources and their stock, built shelters,
people coloured by hunger band, trails, perception boxes, a table of
everybody's needs, and a list of what happened that you can click to jump to
a tick. It reads the saved file and never runs the world.

### Where these systems stop

**In the default world, help only happens when distress is seen.** With
asking switched off, a person in trouble cannot signal and nobody looks for
them. Help depends entirely on a well-supplied person happening to have
someone starving inside their perception radius while nothing of their own is
calling. Offers are consequently rare. Comparing runs with offers on and off across a handful of
seeds showed no overall gain in the number of survivors — slightly fewer, in
fact, within the noise of a few runs. That says the practice does not lift
survival overall; it does not say individual outcomes are unchanged. A unit
carried to a neighbour plainly helps whoever receives it and costs whoever
gave it.

**Nobody remembers a route.** Routing uses only what is in view this tick.
Beyond the perception radius the map is assumed open, so a person walks
confidently into a wall of rough they have crossed a dozen times before and
discovers it again each time. Remembered terrain is the next step in this
domain, and it needs memory.

**Newborns act immediately and independently.** A new person is given a
home, a crowd-yield trait and needs at zero. They are a full adult on their
first tick: they walk, claim, eat, build and can themselves become a parent.
There is no age, no record of who their parents were, and no dependency of
any kind.

**Nobody remembers anything.** Every decision is made from the current
tick's observation. There is no memory of an encounter, a route, a person
who helped, or a source that was empty last time.

**Other present limits.** Scored action selection cannot run alongside water
or warmth, because the scorer has no cases for their actions. The older
isometric viewer in `viewer/` predates water, warmth, terrain, shelters and
births, and shows only one food source. There is no storage, no exchange, no
materials, no weather and no shared rules.

## 2. How we develop: explore the primitives

A primitive is a small rule or capability with a concrete consequence:
seeing something nearby, moving, carrying, consuming, asking, refusing,
transferring, remembering an encounter, sharing shelter, or learning a
route.

Primitives can also describe the environment: travel costs, limited space,
resource depletion, regrowth and exposure to cold.

The larger domains in the next section grow through combinations of these
rules. A single useful primitive may contribute to several domains.

### The way of working

**Start with the world we can watch.** Look for an interesting event, a
repeated frustration, an unused capability, or a situation where people have
too few meaningful choices.

**Explore the rules behind it.** What can people perceive? What can they do?
What does it cost? What changes afterwards? Does that change affect a later
decision?

**Deepen or combine existing primitives where useful.** A small change to
carrying, requests, travel, shelter or memory may enrich several behaviours
at once. Add a new primitive when it provides a useful choice or consequence
that existing rules cannot express.

**Complete the interaction.** Follow it the whole way:

    need or opportunity -> local observation -> decision -> action or refusal
    -> world change -> later decision

A new field, animation or event label is only useful when something in the
world acts on it or experiences its consequences.

**Run the world and watch.** See whether people actually use the capability,
what competes with it, where it fails, and whether anything unexpected
becomes interesting.

**Explore a few meaningful conditions when useful.** Geography, resource
distribution, carrying limits, travel costs, shelter capacity and population
pressure can expose different interactions. Use reproducible runs and
describe which conditions produced what. Avoid adjusting settings solely to
manufacture a desired scene.

**Keep, deepen, simplify or drop the idea.** An interesting surprise may
become the next piece of work. A dull idea may need a better opportunity, a
stronger consequence, or removal. Use judgement rather than mechanically
completing a domain.

### Examples of combinations worth exploring

- Asking, limited supplies and the helper's own hunger can produce selective
  help, refusal or an interrupted rescue.
- A completed transfer, memory and a later partner choice can produce
  recurring cooperation.
- Travel costs, home relocation and shared storage can encourage settlement
  clusters.
- Local depletion, regrowth and remembered routes can change where people
  travel over time.

These are possibilities to explore, not outcomes to arrange. Participants and
outcomes must follow from local rules and actual circumstances.

Implement the small rules explicitly and let larger patterns develop through
their interactions. Do not hardcode particular friendships, successful
rescues, villages, occupations or population collapses.

### Keeping it practical

- No separate primitive registry or new process documents are needed.
- No generic primitive engine or speculative abstraction is required.
- Put behaviour in the subsystem that owns it.
- Use focused tests and relevant checks to protect correctness.
- Judge whether the world became more interesting by watching it.

## 3. Ten development domains

These are connected areas to explore, in our current priority order. We do
not need to finish an entire domain before following a useful interaction
into another one.

### 1. Communication and asking for help

**First behaviour.** A hungry person asks someone nearby for food. The
person asked answers from their own needs and supplies: they help or they
refuse. Follow the request through to delivery, refusal or interruption.
Water requests can follow the same shape once food requests work.

**Primitives.** Asking, answering, refusing, and a reason for the answer.
These join existing perception, distance, carrying, transfer and the
competing needs that already pull people away mid-journey. The existing
offer behaviour is the delivery half of this already: what is missing is
the request that starts it and the answer that may decline it.

**In the viewer.** A request in flight between two people, who was asked and
what they answered, a delivery arriving, and a helper turning back when
their own hunger or thirst becomes the more urgent thing.

### 2. Navigation and exploration

**First behaviour.** A person choosing a route that accounts for the extra
tick rough ground costs, rather than stepping blindly along the longer axis.
Later, exploring for a new source when the ones they know keep failing.

**Primitives.** Route cost, a comparison between routes, and remembered
terrain. These interact with the existing leave-in-time rules, which
currently estimate arrival in straight-line steps and so under-count the
cost of a rough crossing.

**In the viewer.** Trails that bend around rough ground, two people taking
different routes to the same place, worn familiar paths, and a journey into
a part of the map nobody had used.

### 3. Life stages, families and caregiving

**First behaviour.** A newborn recorded with its parents, dependent for a
period, unable to make long trips, and fed by an adult who brings supplies
to it. Maturation into independence, and spacing between births. Ageing can
follow.

**Primitives.** Age, a parent link, dependency, and carrying food to a
specific person rather than to whoever is visibly starving. The last of
those is the same transfer primitive the request work will already have
deepened.

**In the viewer.** A household's workload changing when a child arrives, an
adult making trips on someone else's behalf, a child growing up, and a grown
child leaving to establish a home of its own.

### 4. Social memory and relationships

**First behaviour.** Remembering a small number of actual encounters — who
asked, who helped, who refused — and letting those memories influence whom a
person asks or helps next.

**Primitives.** A short dated memory of encounters, and a partner choice
that reads it. Asking would give memory far more to record — a refusal is a
sharper thing to remember than a gift — which is why asking is the earlier
priority. But memory does not wait on it: the unsolicited gifts that already
happen are real encounters, and could shape who a person walks to next.

**In the viewer.** The same pairs helping each other repeatedly,
reciprocity, someone avoided after a refusal, and a relationship visibly
changing after a particular event.

### 5. Ecology, weather and seasons

**First behaviour.** Food depleting locally where it is taken from and
recovering over time, rather than renewing at a fixed cadence regardless.
Then a simple seasonal effect on growth or on cold.

**Primitives.** Depletion, regrowth and a world-wide condition that changes
over time. These interact with the existing renewal rule and with the
leave-in-time rules, which assume a source will be there when you arrive.

**In the viewer.** A patch worked out and left bare, the same patch
recovering, journeys shifting to wherever is productive now, and a routine
that stops working when the season turns.

### 6. Households and settlement growth

**First behaviour.** Shelters that hold more than one person, with a limit
on capacity, and a real choice about moving home to a better place.

**Primitives.** Shared occupancy, capacity, and relocation. Home is
currently fixed for life and private to one person, so both are new; they
interact with building, warmth and the birth rule, which already places a
newcomer at the nearest free cell.

**In the viewer.** Clusters forming, a shelter at capacity turning someone
away, people moving toward useful places or toward company, and homes left
empty behind them.

### 7. Work, materials and practical skills

**First behaviour.** One complete material chain: gather wood, carry it,
and spend it constructing or repairing something useful. Practice at that
particular task making a person better at it.

**Primitives.** A material with a source and a use, and a per-person skill
that improves with practice. These extend the existing claim, carry and
build primitives — building currently costs only time and consumes nothing.

**In the viewer.** Work trips out and back, a project standing half-finished
while its builder deals with hunger, someone who is visibly the one who
repairs things, and a landscape that shows the work done on it.

### 8. Storage, exchange and specialisation

**First behaviour.** A household store that people physically carry things
into and take things out of. Then carrying limits and spoilage, so a store
is worth having. Then simple barter once different people can produce
different useful things.

**Primitives.** A place that holds resources, carrying limits, decay, and an
exchange between two people. Stores must move resources through the kernel
exactly as claims and transfers already do.

**In the viewer.** A surplus building up, a store running short, hauling
trips, an exchange between two people, and someone visibly dependent on
another person's work.

### 9. Disputes and shared rules

**First behaviour.** Once shared stores and valuable places exist, a small
local agreement about access — taking turns at a source, or contributing to
a shared store — and what people do when it is broken.

**Primitives.** An agreement, a breach, and a response to a breach. These
need the existing crowd-yield behaviour and shared stores to have something
to be about.

**In the viewer.** Turn-taking at a crowded source, an agreement breaking
down, somebody withdrawing from a group, and a different arrangement forming
in its place.

### 10. Culture and knowledge passed between generations

**First behaviour.** One useful thing — a route, a technique, a preference —
that a person can learn by watching someone else do it, and pass on in turn.

**Primitives.** Learning by observation and transmission between people.
This needs memory, and something worth knowing, so it sits last.

**In the viewer.** Different habits in different parts of the map, knowledge
travelling when its holder does, a practice outliving the person who started
it, and a practice disappearing because nobody learned it.

## 4. What to try next

Asking for food is built. It is switched off, and whether the cost it
carries is one we want is an open question rather than a settled no — a world
where people are less often at the edge might pay it easily.

Terrain-aware movement is built and on by default.

**First: childhood and caregiving.**
**Second: remembered terrain**, so a route learned is a route kept, which is
also the first piece of memory the world has ever had.
**Then: whether asking can pay its way**, either in a gentler world or by
making helping cost the helper less time. The world is markedly gentler since
routing landed, so this is worth retrying sooner rather than later.

### What asking looked like, and what it cost

A complete food request, from need to consequence:

1. **Need.** A person is hungry, holds nothing, and either the source is far
   or what they can see of it is empty.
2. **Local observation.** They look at who is within their perception radius
   and identify a possible helper — somebody visibly carrying food. Distance
   matters, because a request they cannot reach is worth less than one they
   can.
3. **Request.** They ask that person. The request is an action with a cost:
   the tick spent on it, and the needs that keep rising while they wait.
4. **Answer.** The person asked decides from their own state. They may help,
   or refuse because they are hungry themselves, because they hold too
   little, or because something of their own is more urgent. A refusal is a
   real outcome with a reason, not a failure.
5. **Delivery or interruption.** If they agree, they close the distance and
   hand over a unit through the kernel, exactly as the existing offer does.
   Their own needs keep rising on the way, so they may turn back before they
   arrive.
6. **Later decision.** A unit that arrives is a chance to eat, not a
   reprieve: the asker still has to spend a tick eating it, and thirst and
   cold have gone on rising throughout. It may also arrive too late to
   matter. Whoever gave is a unit poorer and may need it themselves later.

### How it meets what already exists

The offer behaviour supplies the mechanics of delivery: finding somebody,
walking to them, and transferring a unit through the kernel's settlement
path. It does not supply an agreement. The target is worked out afresh from
the current observation on every tick, and nothing in the world state
records who a helper is on their way to. A helper part-way through a
journey will silently re-pick the nearest visibly starving person, and will
switch recipients if a nearer one appears or drop the errand entirely if the
first one leaves their view.

So a requested delivery needs a little state the offer behaviour has never
needed: an outstanding request, and the agreement it turns into, held long
enough to be completed, refused or interrupted. That is a short-lived record
of one piece of business in progress. It is not the same thing as the social
memory in domain 4, which is about remembering encounters after they have
finished in order to choose differently later.

What asking adds on top of that is the other direction of the exchange: a
person in need choosing a particular helper, and that helper giving an answer
that can be no.

Things worth exploring as it is built: perception radius decides who can be
asked at all; distance decides whether help can arrive in time; carrying
decides whether the helper has anything to give; the helper's own hunger,
thirst and cold compete with the errand and can abandon it mid-way; and the
transfer itself is already governed by the kernel, which can refuse it.

Keep resource transfers in the kernel's settlement path. A helper must
actually possess what they give, and must go on experiencing their own needs
while giving it.

The first addition should be small enough to understand by watching an
ordinary run. Depth should follow from what that run reveals rather than
being designed in advance.

## 5. Making each addition visible and trustworthy

Every addition should show up in the map viewer: requests and the answers to
them, chosen routes, family links, shared stores, changing patches, or
whatever the new behaviour actually is.

The viewer should make it possible to follow one person and understand how
earlier events shaped what they do next. It must show real world behaviour
read from the saved run, never a second calculation of what the world
decided.

These guarantees stay:

- Resource gains and losses have explicit causes.
- Settlement owns balance changes.
- Observation cannot mutate world state.
- Runs remain deterministic from a seed.
- People decide by rules, with no AI-generated choices at runtime.

Keep the emphasis on watching the world and following what is interesting.
No orchestrators, evidence pipelines, verification frameworks or
run-management systems.
