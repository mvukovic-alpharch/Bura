from __future__ import annotations
from copy import deepcopy
from datetime import date,datetime,timezone
import json
import uuid


STATE_FIELDS=("fixtures","dfs_players","salaries","eligibility","market_observations","lineup_observations","injury_observations","model_versions","projections","simulations","optimizer_results","data_freshness","data_quality")


def new_slate_state(slate_id:str,slate_date:str|date,platform="DraftKings") -> dict:
    state={"slate_id":slate_id,"slate_date":str(slate_date),"platform":platform,"current_workflow_state":"NEW","state_version":0,"last_actions":[]}
    for field in STATE_FIELDS: state[field]={} if field in {"salaries","eligibility","model_versions","projections","simulations","optimizer_results","data_freshness","data_quality"} else []
    return state


def load_slate_state(con,slate_id,slate_date=None,platform="DraftKings"):
    row=con.execute("SELECT state_json FROM slate_states WHERE slate_id=? ORDER BY state_version DESC LIMIT 1",[slate_id]).fetchone()
    return json.loads(row[0]) if row else new_slate_state(slate_id,slate_date or date.today(),platform)


def save_slate_state(con,state):
    now=datetime.now(timezone.utc); state=deepcopy(state); state["state_version"]=int(state.get("state_version",0))+1; state["updated_at"]=now.isoformat()
    con.execute("DELETE FROM slate_states WHERE slate_id=?",[state["slate_id"]])
    con.execute("INSERT INTO slate_states VALUES (?,?,?,?,?,?,?,?)",[state["slate_id"],state["slate_date"],state["platform"],json.dumps(state,default=str),state["current_workflow_state"],state.get("data_quality",{}).get("status"),now,state["state_version"]])
    return state


def journal(con,slate_id,action,reason,inputs=None,outputs=None,model_version=None,data_timestamp=None,result=None,status="completed"):
    item={"journal_id":str(uuid.uuid4()),"timestamp":datetime.now(timezone.utc),"slate_id":slate_id,"action":action,"reason":reason,"inputs":inputs or {},"outputs":outputs or {},"model_version":model_version,"data_timestamp":data_timestamp or datetime.now(timezone.utc),"result":result,"status":status}
    con.execute("INSERT INTO decision_journal VALUES (?,?,?,?,?,?,?,?,?,?,?)",[item["journal_id"],item["timestamp"],slate_id,action,reason,json.dumps(item["inputs"],default=str),json.dumps(item["outputs"],default=str),model_version,item["data_timestamp"],str(result) if result is not None else None,status]); return {**item,"timestamp":item["timestamp"].isoformat(),"data_timestamp":item["data_timestamp"].isoformat()}


def record_hypothesis(con,slate_id,hypothesis,evidence,status="open"):
    identifier=str(uuid.uuid4()); now=datetime.now(timezone.utc)
    con.execute("INSERT INTO research_hypotheses VALUES (?,?,?,?,?,?)",[identifier,now,slate_id,hypothesis,json.dumps(evidence,default=str),status]); return identifier
