"""position_hub — positional role attribution for the Carolina Panthers.

The question: not "what position is he listed at" (PFF gives one label per snap), but "what does
he actually play". Every defender-snap gets a probability vector over roles from NGS tracking
geometry + PFF charting context; player-seasons aggregate to a role mix (70% free safety, 20% box
safety, 10% slot) with percentiles against position peers.
"""
__version__ = "0.1.0"
