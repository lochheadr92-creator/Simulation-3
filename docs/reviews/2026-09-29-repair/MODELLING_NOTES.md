# Existing rules clarified during the review repair

These are the rules at the reviewed `fe940ef` repair. Subsequent local work
on 2026-09-30 adds a bounded witnessed-death response and boolean validation;
see [current development directions](../../../WORLD_DIRECTIONS.md). The
historical waiting-after-death description below predates that addition.

These notes explain existing behaviour; they do not introduce simulation rules.

- **Knowledge sharing needs shared homes and contact.** A listener must share the speaker's home and be visible within one Chebyshev cell. Source memory is a validated dependency. Generated homes-off worlds give people separate homes, so enabling sharing alone can record firsthand sightings without anyone hearing a report. Use `--source-memory on --knowledge-sharing on --homes on` for a generated-world sharing example. It still needs encounters and a recent empty-source sighting; speech is not guaranteed.
- **A food promise can outlive its speaker briefly.** Household food expectations use the existing 12-tick expiry and local cache/return evidence. Death is not currently represented as witnessed information for this rule, even if it occurred nearby. The listener can wait until expiry. Adding witnessed death would extend the observation model.
- **Dead people retain their holdings.** Their accounts remain in resource totals. No rule currently redistributes, scavenges or deletes those units. Conservation includes them, although living people cannot collect them.
- **Configuration types and values are separate.** Scalar integer settings require actual integers, including inactive settings; booleans and numeric strings are rejected. Negative integer seeds, zero perception and zero hunger rate are supported. Existing range and dependency validation still applies. Settings for disabled extensions may be omitted from saved descriptions and restored to defaults; the active saved rules, not every inactive dataclass value, must round-trip.
- **World ticks and decision ticks label different boundaries.** World tick 0 is genesis. World tick k displays the result of decision tick k-1. Deep selection/settlement text uses decision ticks; the HUD and timeline label world ticks. Stored numbering is unchanged.
- **`held` means movement delay.** It records remaining rough-ground delay, not carried food. Ordinary movement creates a one-tick delay. The controlled social-memory fixture uses an artificial larger delay to isolate a rule; it is not an ordinary-world example.
- **Social memory is a preference among eligible people, not a new source of help.** Gifts can be remembered without changing a later action: the donor must be visible and eligible, there must be a different otherwise-preferred recipient, and helping must survive personal-need priorities. The fixed 35-seed sweep found no activation by tick 400 under either departure estimate; at 780 it occurred in three current worlds and four old-estimate worlds. This sample does not establish universal absence, prevalence or survival benefit.
