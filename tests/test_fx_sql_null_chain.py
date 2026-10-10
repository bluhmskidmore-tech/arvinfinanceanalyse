"""B1 synthetic storage -> real HTTP plus direct non-UI read consumers."""
from __future__ import annotations
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
import json
import duckdb
import pytest
from fastapi.testclient import TestClient
from backend.app.services import macro_vendor_service as service
from tests.test_fx_analytical_fallback_api import DAY, ENDPOINT, USD_NAME, _app, _observation, _seed

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_market_data]

@pytest.fixture
def http(tmp_path, monkeypatch):
    settings=SimpleNamespace(duckdb_path=str(tmp_path/'synthetic.duckdb'))
    with TestClient(_app(settings,monkeypatch), raise_server_exceptions=False) as client:
        yield SimpleNamespace(path=Path(settings.duckdb_path),client=client)

def seed(path, values, name=USD_NAME):
    rows=[_observation(DAY-timedelta(days=i),value,f'observation_{i}') for i,value in enumerate(values)]
    _seed(path,[('synthetic-fx',name,rows)])
    return rows

def point(body): return body['result']['groups'][0]['series'][0]

@pytest.mark.parametrize('values,selected', [([None,7.2,7.1],1),([7.2,None,7.1],0)])
def test_sql_null_latest_and_prior_real_http(http,values,selected):
    rows=seed(http.path,values)
    response=http.client.get(ENDPOINT)
    assert response.status_code==200,response.text
    body=response.json(); p=point(body)
    assert (p['trade_date'],p['value_numeric'],p['source_version'],p['vendor_version'])==rows[selected][:4]
    assert p['latest_change'] is None
    assert [r['value_numeric'] for r in p['recent_points']]==values
    assert p['quality_flag']==body['result_meta']['quality_flag']=='warning'
    assert body['result_meta']['filters_applied']['warnings']
    json.dumps(body,allow_nan=False)

@pytest.mark.parametrize('values',[[None,None],[0,-1]])
def test_all_unavailable_has_domain_503(http,values):
    seed(http.path,values)
    response=http.client.get(ENDPOINT)
    assert response.status_code==503,response.text
    assert response.json()['detail']['code']=='fx_analytical_unavailable'
    assert 'no valid input rows' in response.json()['detail']['message']

@pytest.mark.parametrize('state',['corrupt','broken_schema'])
def test_read_failure_is_not_empty_success(http,state):
    if state=='corrupt': http.path.write_bytes(b'synthetic-corrupt')
    else:
        seed(http.path,[])
        with duckdb.connect(str(http.path)) as conn: conn.execute('alter table fact_choice_macro_daily drop column value_numeric')
    response=http.client.get(ENDPOINT)
    assert response.status_code==503,response.text
    assert response.json()['detail']['code']=='fx_analytical_read_failed'

@pytest.mark.parametrize('values',[[None,0,-1],[0,None,-1],[-1,0,-2]])
def test_swap_null_is_missing_and_zero_negative_are_valid(http,values):
    seed(http.path,values,'synthetic C-Swap')
    response=http.client.get(ENDPOINT)
    assert response.status_code==200,response.text
    p=point(response.json())
    assert p['value_numeric']==values[0]
    assert p['latest_change']==(None if None in values[:2] else values[0]-values[1])
    assert [r['value_numeric'] for r in p['recent_points']]==values

@pytest.mark.parametrize('values',[[None,7.2],[7.2,None]])
def test_macro_direct_consumer_retains_fx_null(http,values):
    seed(http.path,values)
    body=service.choice_macro_latest_envelope(str(http.path))
    p=body['result']['series'][0]
    assert p['value_numeric']==values[0]
    assert p['latest_change'] is None
    assert [r['value_numeric'] for r in p['recent_points']]==values

@pytest.mark.parametrize('values',[[None,7.2],[7.2,None]])
def test_real_coverage_and_agent_consumers_keep_fx_missing(http, values, monkeypatch):
    from backend.app.agent.schemas.agent_request import AgentQueryRequest
    from backend.app.services.agent_service import _market_data_payload
    seed(http.path,values)
    # The catalog location is synthetic; every financial read uses the real reader.
    monkeypatch.setattr(service,'get_settings',lambda:SimpleNamespace(choice_macro_catalog_file=str(http.path.parent/'missing-catalog.json')))
    coverage=service.market_data_coverage_summary_envelope(str(http.path))
    section=next(row for row in coverage['result']['sections'] if row['key']=='fx_analytical')
    assert section['row_count']==1
    assert section['quality_flag']=='warning'
    agent=_market_data_payload(AgentQueryRequest(question='synthetic market data',basis='analytical'),str(http.path))
    macro=next(card for card in agent['cards'] if card['title']=='Latest Macro Series')['data'][0]
    assert macro['value_numeric']==values[0]
    assert macro['latest_change'] is None
    assert [p['value_numeric'] for p in macro['recent_points']]==values

@pytest.mark.parametrize('quality',['warning','stale','error'])
def test_fallback_does_not_downgrade_selected_quality(http,quality):
    rows=[_observation(DAY,None,'missing'),_observation(DAY-timedelta(days=1),7.2,'selected',quality)]
    _seed(http.path,[('synthetic-fx',USD_NAME,rows)])
    response=http.client.get(ENDPOINT)
    assert response.status_code==200,response.text
    assert point(response.json())['quality_flag']==response.json()['result_meta']['quality_flag']==quality

@pytest.mark.parametrize('consumer',['coverage','agent'])
def test_unavailable_propagates_through_real_non_ui_consumers(http,consumer,monkeypatch):
    from backend.app.core_finance.fx_rates import FxRateUnavailableError
    from backend.app.agent.schemas.agent_request import AgentQueryRequest
    from backend.app.services.agent_service import _market_data_payload
    seed(http.path,[None,None])
    monkeypatch.setattr(service,'get_settings',lambda:SimpleNamespace(choice_macro_catalog_file=str(http.path.parent/'missing-catalog.json')))
    with pytest.raises(FxRateUnavailableError,match='no valid input rows'):
        if consumer=='coverage': service.market_data_coverage_summary_envelope(str(http.path))
        else: _market_data_payload(AgentQueryRequest(question='synthetic market data',basis='analytical'),str(http.path))
    if consumer=='coverage':
        response=http.client.get('/ui/market-data/coverage-summary')
        assert response.status_code==503,response.text
        assert response.json()['detail']['code']=='fx_analytical_unavailable'

def test_http_fixture_for_actual_frontend_replay(http):
    import os
    rows=seed(http.path,[None,7.2,7.1])
    response=http.client.get(ENDPOINT)
    assert response.status_code==200,response.text
    p=point(response.json())
    assert p['value_numeric']==rows[1][1] and p['recent_points'][0]['value_numeric'] is None
    output=os.environ.get('FX_HTTP_FIXTURE')
    if output:
        Path(output).write_text(json.dumps(response.json(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

@pytest.mark.parametrize('values',[[None,7.2],[7.2,None],[7.2,0],[7.2,-1]])
def test_macro_consumer_uses_catalog_fx_identity_and_safe_comparator(http,values):
    seed(http.path,values)
    with duckdb.connect(str(http.path)) as conn:
        conn.execute("update fact_choice_macro_daily set series_name='provider raw alias'")
    body=service.choice_macro_latest_envelope(str(http.path))
    p=body['result']['series'][0]
    assert p['value_numeric']==values[0]
    assert p['latest_change'] is None
    assert [p['value_numeric'] for p in p['recent_points']]==values

@pytest.mark.parametrize('active_present',[True,False])
def test_sql_null_real_publication_g1_g2_g1_keeps_selected_identity(tmp_path,monkeypatch,active_present):
    from tests import test_fx_selected_availability_api_review as fixtures
    from backend.app.repositories.system_read_publication_repo import SYSTEM_READ_GENERATION_HEADER
    original=fixtures._series
    def null_latest(number,style):
        series=original(number,style)
        sid,name,rows=series[0]
        rows[0]=(*rows[0][:1],None,*rows[0][2:])
        return [(sid,name,rows)]
    monkeypatch.setattr(fixtures,'_series',null_latest)
    chain=fixtures._published_chain(tmp_path,monkeypatch)
    if not active_present: chain.active.unlink()
    with TestClient(chain.app) as client:
        bodies=[]
        for number,generation in [(1,chain.g1[0]),(2,chain.g2[0]),(1,chain.g1[0])]:
            response=fixtures._request(client,generation)
            assert response.status_code==200,response.text
            assert response.headers[SYSTEM_READ_GENERATION_HEADER]==generation
            body=response.json(); p=point(body)
            assert p['recent_points'][0]['value_numeric'] is None
            assert p['value_numeric']==6+number
            assert p['source_version']==f'sv_synthetic_review_G{number}_selected'
            assert p['trade_date']==str(DAY-timedelta(days=number))
            assert p['latest_change'] is None
            bodies.append(body)
    assert bodies[0]['result']==bodies[2]['result']
    assert chain.active.exists() is active_present

def test_true_empty_and_all_null_swap_are_distinct(http):
    response=http.client.get(ENDPOINT)
    assert response.status_code==200
    assert response.json()['result']['groups']==[]
    seed(http.path,[None,None],'synthetic C-Swap')
    response=http.client.get(ENDPOINT)
    assert response.status_code==200
    p=point(response.json())
    assert p['value_numeric'] is None and p['latest_change'] is None
    assert len(p['recent_points'])==2
    assert p['quality_flag']=='warning'
