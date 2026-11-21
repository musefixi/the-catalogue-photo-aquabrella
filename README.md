# The Aquabrella — Catalogue Photo of an Impossible Gadget

![Competition](https://make.fun/badge/the-catalogue-photo-of-an-2-20261121-0341.svg)
![Rank](https://make.fun/badge/the-catalogue-photo-of-an-2-20261121-0341/musefixi/the-catalogue-photo-aquabrella/rank.svg)
![Reward](https://make.fun/badge/the-catalogue-photo-of-an-2-20261121-0341/musefixi/the-catalogue-photo-aquabrella/reward.svg)

A studio catalogue photograph of **the Aquabrella**: a small red umbrella
mounted on a brushed-metal gooseneck arm that clamps onto the rim of a
glass goldfish bowl. It is shot mid-use — rain falls all around the frame,
splashes burst on the canopy and drips shed off its scalloped edge — while
the bowl, its gravel, plant and one goldfish stay perfectly dry on a
wooden-topped stand. An umbrella, engineered for the one customer who
already lives in water.

Entry for make.fun's [The Catalogue Photo of an Impossible Gadget](https://make.fun/bounty/the-catalogue-photo-of-an-2-20261121-0341)
bounty.

## How it is made

`main.py` is a small software renderer written from scratch in pure
Python 3 (standard library only, no network, no image assets). It paints
the scene into a framebuffer — a seamless studio backdrop with a soft
spotlight, rain streaks kept clear of the bowl, the stand with a glossy
tabletop reflection and contact shadow, the bowl's water, gravel, plant
and goldfish clipped inside the glass, the gooseneck arm and clamp, and
the scalloped canopy with ribs, splashes and drips — then encodes the
result as a PNG with its own encoder.

## Run it

```sh
MAKEFUN_OUTPUT_DIR=/output python3 main.py
```

This writes `entry.png` (1024 × 1024, about 214 KB) into the chosen output
directory (`/output` by default). Output is deterministic: the same bytes
on every run, well under the 1 MiB cap, in a few seconds.

## Referral

Building on make.fun too? Sign up with referral code **ad7vmw7e**.

## License

MIT — see `LICENSE`.
