# Plan

1. Claude independently reviews the numbered contract before implementation; no code while unresolved
2. Grok copies planner af157463 into its owned prefix and writes failing public-seam tests mapped to clauses
3. Implement the smallest versioned validation/projection/rendering changes while preserving v1 exactly
4. Record RED/GREEN, meaningful kills, source pins and bounded owned-child receipts; submit only the seven owned paths
5. Claude final Spec and ZCode final Standards review the immutable candidate in their own copies
6. Codex integrates only reviewed paths, runs full actual-main Windows suite/checks under host-heavy, then separately commits and publishes branch1/PR2
