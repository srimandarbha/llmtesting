from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text
from typing import List, Dict
import json
from ..dependencies import db_session
router = APIRouter(prefix="/clusters", tags=["CVE Advisor"])

# Weights for severity to calculate risk score
SEVERITY_WEIGHT = {
    "Critical": 10,
    "Important": 5,
    "Moderate": 2,
    "Low": 1
}
MAX_RISK_BASELINE = 30 # Arbitrary threshold to represent 100% risk for normalization

def calculate_risk_percent(cves: list) -> int:
    score = sum(SEVERITY_WEIGHT.get(cve.get("severity", "Low"), 1) for cve in cves)
    percent = min(100, int((score / MAX_RISK_BASELINE) * 100))
    return percent

@router.get("")
async def list_clusters(db: AsyncSession = Depends(db_session)):
    result = await db.execute(text("SELECT cluster_id AS id, name, openshift_version AS current_version FROM clusters;"))
    clusters = result.fetchall()
    
    output = []
    for c in clusters:
        cluster_dict = dict(c._mapping)
        active_cves_result = await db.execute(
            text("SELECT severity FROM rhokp_cve_knowledge WHERE affected_versions @> :ver"),
            {"ver": f'"{cluster_dict["current_version"]}"'}
        )
        current_cves = [dict(r._mapping) for r in active_cves_result]
        cluster_dict["risk_percent"] = calculate_risk_percent(current_cves)
        output.append(cluster_dict)
        
    return output

@router.get("/{cluster_id}/upgrade-advisor")
async def get_upgrade_advisor(cluster_id: str, db: AsyncSession = Depends(db_session)):
    # 1. Fetch cluster
    result = await db.execute(
        text("SELECT openshift_version AS current_version FROM clusters WHERE cluster_id = :id"),
        {"id": cluster_id}
    )
    cluster = result.fetchone()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
        
    cluster_dict = dict(cluster._mapping)
    current_version = cluster_dict["current_version"]
    
    # 2. Fetch all CVEs currently affecting this cluster
    # Using JSONB containment operator `@>` for affected_versions
    active_cves_result = await db.execute(
        text("SELECT advisory_id, severity, cves, raw_text FROM rhokp_cve_knowledge WHERE affected_versions @> :ver"),
        {"ver": f'"{current_version}"'}
    )
    current_cves = [dict(r._mapping) for r in active_cves_result]
    current_risk_percent = calculate_risk_percent(current_cves)

    # 3. Define target paths
    parts = current_version.split('.')
    if len(parts) != 3:
        raise HTTPException(status_code=400, detail="Invalid version format")
        
    # We evaluate +2 patches up, and +1 minor up based on our mock data structure
    targets = [
        {"version": f"{parts[0]}.{parts[1]}.{int(parts[2]) + 1}", "type": "patch"},
        {"version": f"{parts[0]}.{parts[1]}.{int(parts[2]) + 2}", "type": "patch"},
        {"version": f"{parts[0]}.{int(parts[1]) + 1}.0", "type": "minor"}
    ]
    
    paths = {}
    best_target = None
    lowest_risk = 101

    for target in targets:
        t_version = target["version"]
        
        # Risks Waiting: CVEs that explicitly affect the target version
        waiting_result = await db.execute(
            text("SELECT advisory_id, severity, cves, raw_text FROM rhokp_cve_knowledge WHERE affected_versions @> :ver"),
            {"ver": f'"{t_version}"'}
        )
        risks_waiting = [dict(r._mapping) for r in waiting_result]
        residual_risk_percent = calculate_risk_percent(risks_waiting)
        
        # Resolves: CVEs affecting the current version but NOT the target version
        waiting_advisory_ids = {w["advisory_id"] for w in risks_waiting}
        resolves = [cve for cve in current_cves if cve["advisory_id"] not in waiting_advisory_ids]
        
        # Track Best Upgrade
        if residual_risk_percent < lowest_risk:
            lowest_risk = residual_risk_percent
            best_target = t_version
            
        paths[t_version] = {
            "version": t_version,
            "type": target["type"],
            "residual_risk_percent": residual_risk_percent,
            "resolves": resolves,
            "risks_waiting": risks_waiting,
            "description": f"Upgrading to {t_version} leaves {len(risks_waiting)} known risks."
        }
        
    return {
        "current_version": current_version,
        "current_risk_percent": current_risk_percent,
        "current_cves": current_cves,
        "best_upgrade": best_target,
        "paths": paths
    }
