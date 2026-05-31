# CVE Upgrade Advisor: Decision Matrix & Algorithm

If the "Residual Risk" percentage looks surprisingly high (or even higher than your current risk) for certain upgrade paths, it is actually the algorithm working exactly as intended! Here is a transparent breakdown of how the engine calculates those percentages and flags the "Best Choice."

## 1. Severity Weighting 
Every vulnerability actively affecting a version is assigned a mathematical weight based on its Red Hat Severity rating:
- **Critical:** 10 points
- **Important:** 5 points
- **Moderate:** 2 points
- **Low:** 1 point

## 2. Risk Percentage Calculation
The total sum of these weights is divided by a hardcoded **Maximum Risk Baseline** (currently set to `30` points for visualization purposes) and capped at 100%.
```
Risk % = min(100, (Sum of Weights / 30) * 100)
```
*Example: A version with 2 Criticals (20) and 1 Important (5) scores 25. 25 / 30 = 83% Risk.*

## 3. The "Residual Risk" (Risks Waiting)
When evaluating a future target version (e.g., `4.20.16`), the engine does **not** just look at what is being fixed. It actively scans the database for all vulnerabilities that *still affect* the target version. 

**Why would Residual Risk be high?**
- **Unpatched Zero-Days:** If there is a critical zero-day affecting all `4.20.x` streams, upgrading to a higher patch will NOT eliminate it. That CVE becomes a "Risk Waiting", and its score is added to the target version's Residual Risk.
- **Early Release Bugs:** Upgrading to a major early release (like `4.21.0-rc1`) might resolve old bugs, but it often introduces *new* critical vulnerabilities specific to that release. The algorithm penalizes the target version for these new risks!

## 4. The "Best Choice" Decision Matrix
The backend dynamically evaluates multiple semantic upgrade paths (Patch +1, Patch +2, and Next Minor). 

The `⭐ Best Choice` badge is awarded using a strict minimizing function:
1. It calculates the **Residual Risk %** for every possible target.
2. It completely ignores how many CVEs are *resolved*. It strictly prioritizes the **lowest absolute remaining risk**.
3. It selects the target version with the lowest Residual Risk %.

If a minor release introduces new critical bugs, the algorithm will intelligently suggest a lower patch version as the "Best Choice" because it mathematically yields a safer overall cluster posture!
