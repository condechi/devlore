# demo/ — reproducible README GIFs

The GIFs are rendered from [vhs](https://github.com/charmbracelet/vhs) tapes so they can
be re-rendered any time the UI changes:

```bash
brew install vhs
cd demo
vhs hero.tape        # → hero.gif      (the README hero: `devlore add .` end-to-end)
vhs receipts.tape    # → receipts.gif  (cited answers + live code pointers + self-doubt)
```

Honesty note: the playback scripts (`play-*.sh`) replay **canned output that mirrors the
real tool's output shapes**, time-compressed — a 14-conversation backfill takes minutes of
LLM time that nobody wants to watch in a GIF. Run `devlore add .` on your own repo for the
real thing, costs shown up front.
