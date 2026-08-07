# Preweek Technical Documentatoin

## Technical Goal
Experiment different Agent Architectures so that we can see which best fits our business use case.

- Agent file w/ referenced files
- Agent skills driven by main agent (e.g. ~/.skills)
- File system subagent driven by coding harness
- AI workflow automation platform
- Generic AI agent SDK
- Use low leel first-party LLM sdks
- Use REST APIs directly, write our agentic loop

## Technical Uncertainty
- Not sure what augments in prompt to raw LLM interactions (leveraging tools) is sufficient for business case.
- I'm uncertain if coding harness agentic loop is enough to successfully drive non-coding workloads.
- Not sure if AI thinking mode and parameter setting if sufficient enough to hold memory and drive decisions for our business case.
- Not sure that coding harness can interact with a MUD without interface or SDK managing telnet session (seems working for now).

## Technical Hypotheses
- Andrew suspects we probably will need to have a reliable interface to interact with the MUD b/c managing live-sessions in the past was challenging.
- Gemma4B might not be sufficient - specialized agentic loop will probably be necessary.
- We'll need to roll-our-own agent without SDK b/c we want generic primitives for o11y, memmory, and other tools for our specialized implementation.

## Technical Observations
- Qwen/Gemma really struggled to connect to the MUD - it fumbles with scripts and is unreliable in creating a connection.
- Using Markdown files where coding harness updates as simple memory wasn't effective. It saves navigation -

> Example of AI using agent skill and a MD managing state to map out the world:
## Newbie Zone map (partial — verified in-game)
```
[Great Field] --w-- [Entrance]
                      |
                      n
              [Beginning Of The Passage]  *** LAST SEEN HERE ***
                      |
                      e
              [Dirty Hallway]  (door s → Small Room; e → Nexus)
                      |
                      e
              [A Nexus]  N → Bright Hallway / stairs wing; E door; S → More Hallway
                      |
                      s
              [More Of The Hallway] --w-- [A Small Room] (locked grate down)
                      |
                      s
              [Another Corner] --e door-- [Alchemist's Room]
                      |
                      w → Brighter Hallway (partial)

Bright wing (via Nexus n):
  [Bright Hallway] → [North Stairs] / [South Stairs]
       | up
  [Balcony] (n/s ends, scenic only)
  [The Hallway] (banners) ↔ [Statue's Room]
  [Narrow Passage] → [Alchemist's Room] (Newbie Alchemist)
```

## Technical Conclusions
- Skills and subagents are capable of driving the MUD.
- Need specialized memory for map nav and world data
- We opened new technical use-case of if should have agent handle multiple sessions of multiple player
- Implementing our own specialized loops remain technical uncertain - needs to be explored Week 2.
- No customized agentic loop - agents couldn't perform goals efficiently. We didn't have key meta strategies or journey player strategies.

# Key Takeaway
With specialized use-cases like playing MUD, we need specialized tooling and agentic loops.