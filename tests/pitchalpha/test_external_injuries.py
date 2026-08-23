from datetime import datetime, timedelta, timezone
import hashlib
import json

from openpyxl import Workbook

from pitchalpha.external_injuries import ingest_external_injuries, normalize_external_status
from pitchalpha.orchestrator import PitchAlphaOrchestrator
from pitchalpha.schema import connect
from pitchalpha.slate_state import load_slate_state, new_slate_state, save_slate_state
from pitchalpha.telegram import handle_text


def workbook(path,rows):
    book=Workbook(); sheet=book.active; sheet.append(["Player","Team","Pos","Injury","Status","Est. Return"])
    for row in rows:sheet.append(row)
    book.save(path)


def seed_player(con,pid,name,team="ARS"):
    con.execute("INSERT INTO players VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",[pid,name,None,None,None,None,None,None,None,False,datetime.now(timezone.utc),"seed"])
    con.execute("INSERT INTO player_squads VALUES (?,?,?,?,?,?,?,?,?)",[pid,name,1,"Arsenal",team,"Midfielder",None,datetime.now(timezone.utc),"seed"])


def seed_live_state(con,pid=1,name="Ollie Watkins",team="ARS",p_start=.88):
    con.execute("INSERT INTO dfs_players VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",["s","1",f"af:{pid}",pid,name,name.lower().replace(" ",""),team,"CHE","",7000,"",None,1.,"seed",datetime.now(timezone.utc),"seed"])
    state=new_slate_state("s","2026-08-22"); state["current_workflow_state"]="FINAL"; state["dfs_players"]=[{"player_id":str(pid),"name":name,"salary":7000}]; state["projections"]={str(pid):{"player_id":pid,"name":name,"p_start":p_start,"expected_minutes":71,"mean":10,"p90":20,"salary":7000}}; state["data_quality"]={"status":"GREEN","failures":[],"warnings":[]}; save_slate_state(con,state)


def test_status_normalization_preserves_uncertainty():
    assert normalize_external_status("GTD")=="QUESTIONABLE"
    assert normalize_external_status("OUT")=="OUT"
    assert normalize_external_status("SUS")=="SUSPENDED"
    assert normalize_external_status("maybe")=="UNKNOWN"


def test_xlsx_ingestion_archive_reconciliation_duplicate_and_qa(tmp_path):
    source=tmp_path/"injuries.xlsx"; workbook(source,[("Ollie Watkins","ARS","F","Knock","GTD","2026-08-22"),("Ollie Watkins","ARS","F","Knock","GTD","2026-08-22")]); original=hashlib.sha256(source.read_bytes()).hexdigest()
    with connect(tmp_path/"db.duckdb") as con:
        seed_player(con,1,"Ollie Watkins"); seed_live_state(con)
        result=ingest_external_injuries(con,source,tmp_path/"raw",tmp_path/"processed",slate_id="s",now=datetime(2026,8,19,tzinfo=timezone.utc))
        assert result["total_rows"]==2 and result["stored_rows"]==1 and result["matched"]==1 and len(result["duplicates"])==1
        archive=result["source_archive"]; assert hashlib.sha256(open(archive,"rb").read()).hexdigest()==original
        row=con.execute("SELECT source,status_raw,status,estimated_return_raw,match_confidence FROM external_injury_observations").fetchone(); assert row[:4]==("external_manual","GTD","QUESTIONABLE","2026-08-22") and row[4]>=.97
        state=load_slate_state(con,"s"); assert state["data_quality"]["status"]=="YELLOW" and "run_opportunity_models" in state["pending_actions"]
        assert con.execute("SELECT count(*) FROM anomaly_investigations WHERE recommendation='opportunity_review'").fetchone()[0]==1


def test_ambiguous_match_never_silently_accepted(tmp_path):
    source=tmp_path/"ambiguous.xlsx"; workbook(source,[("Alex Smith","","M","Knock","OUT","")])
    with connect(tmp_path/"db.duckdb") as con:
        seed_player(con,1,"Alex Smith","AAA"); seed_player(con,2,"Alex Smith","BBB")
        result=ingest_external_injuries(con,source,tmp_path/"raw",tmp_path/"processed",now=datetime(2026,8,19,tzinfo=timezone.utc))
        assert result["matched"]==0 and result["ambiguous"]==1 and result["manual_review"][0]["reason"]=="ambiguous"
        assert con.execute("SELECT internal_player_id FROM external_injury_observations").fetchone()[0] is None


def test_changed_status_detection_and_unchanged_deduplication(tmp_path):
    source=tmp_path/"injuries.xlsx"
    with connect(tmp_path/"db.duckdb") as con:
        seed_player(con,1,"Ollie Watkins"); seed_live_state(con); start=datetime(2026,8,19,tzinfo=timezone.utc)
        workbook(source,[("Ollie Watkins","ARS","F","Knock","GTD","")]); first=ingest_external_injuries(con,source,tmp_path/"raw",tmp_path/"processed",slate_id="s",now=start)
        same=ingest_external_injuries(con,source,tmp_path/"raw",tmp_path/"processed",slate_id="s",now=start+timedelta(minutes=1))
        workbook(source,[("Ollie Watkins","ARS","F","Knock","OUT","")]); changed=ingest_external_injuries(con,source,tmp_path/"raw",tmp_path/"processed",slate_id="s",now=start+timedelta(minutes=2))
        assert len(first["changes"])==1 and same["changes"]==[] and len(changed["changes"])==1
        assert changed["changes"][0]["changes"][0]["before"]=="QUESTIONABLE" and changed["changes"][0]["changes"][0]["after"]=="OUT"
        assert changed["comparison_conflicts"][0]["disagreement_priority"]=="HIGH"
        assert con.execute("SELECT count(*) FROM external_injury_observations").fetchone()[0]==3


def test_orchestrator_routing_and_telegram_injury_reporting(tmp_path):
    source=tmp_path/"injuries.xlsx"; workbook(source,[("Ollie Watkins","ARS","F","Knock","OUT","")])
    with connect(tmp_path/"db.duckdb") as con:
        seed_player(con,1,"Ollie Watkins"); seed_live_state(con); result=ingest_external_injuries(con,source,tmp_path/"raw",tmp_path/"processed",slate_id="s",now=datetime(2026,8,19,tzinfo=timezone.utc)); state=load_slate_state(con,"s")
        config={"qa":{"max_age_minutes":{},"max_cold_start_fraction":1},"anomaly":{}}; actions=PitchAlphaOrchestrator(con,config).determine_actions(state)
        assert "run_opportunity_models" in actions and "run_fantasy_models" in actions and "run_simulation" in actions
        changes=handle_text(con,"1","/changes","1","s"); why=handle_text(con,"1","/why Ollie Watkins","1","s"); status=handle_text(con,"1","/status","1","s"); report=handle_text(con,"1","/report","1","s")
        assert "INJURY CHANGE" in changes and "External status: OUT" in changes
        assert "External OUT" in why and "Injury disagreements: 1" in status and "INJURY CHANGE" in report
        journal=json.loads(con.execute("SELECT outputs FROM decision_journal WHERE action='external_injury_change'").fetchone()[0]); assert "run_opportunity_models" in journal["affected_actions"]
