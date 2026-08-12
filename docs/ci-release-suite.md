# CI 鍚庣 Release Suite 娓呭崟

- 鏉冨▉鏉ユ簮锛歚scripts/backend_release_suite.py` 鐨勫父閲?`RELEASE_SUITE_TESTS`銆乣GOVERNANCE_MCP_FAST_SUITE_TESTS`銆乣GOVERNANCE_MCP_FULL_SUITE_TESTS`銆乣EXECUTIVE_RELEASE_SAMPLE_IDS`
- 鏈枃妗ｆ€ц川锛氫笂杩板父閲忕殑**鍙楁帶闈欐€侀暅鍍?*锛堜緵璇勫涓庢绱紝涓嶆槸绗簩浜嬪疄婧愶級
- 蹇収鏃ユ湡锛?026-08-12锛坰uite_name锛歚governed-phase2-backend-release-suite`锛?- 闂ㄧ鍒嗗眰鑳屾櫙涓庣洸鍖哄垎鏋愶細瑙?`docs/plans/tech-debt-remediation/B0-ci-gate-layering.md`

## 1. 鍦?CI 涓殑浣嶇疆

| 鐜妭 | 鍐呭 |
| --- | --- |
| 瑙﹀彂 | `.github/workflows/ci.yml` 鐨?`backend` job锛坄pull_request` 鈫?main锛沗push` 鈫?main / `codex/**`锛夛紝姝ラ `Run bounded backend release suite`锛歚python scripts/backend_release_suite.py` |
| 绗竴闃舵 | `python -m pytest -q <涓嬫柟 30 涓枃浠?` |
| 绗簩闃舵 | 娌荤悊 MCP 鍚堢害锛氶粯璁?fast profile锛宍python -m pytest -q -m mcp_fast tests/test_project_mcp_fast_contracts.py` |
| 鍚?job 琛ュ厖姝ラ | agent harness + 闂ㄧ鏄犲皠瀹堝崼锛?*涓嶅湪 release suite 鑴氭湰鍐?*锛夛細`python -m pytest -q tests/test_agent_eval_spec.py tests/test_agent_eval_reward.py tests/test_agent_eval_collect.py tests/test_agent_eval_scoring_integrity.py tests/test_agent_eval_replay.py tests/test_agent_eval_pr_replay.py tests/test_agent_eval_rollout.py tests/test_agent_eval_coverage_report.py tests/test_caliber_gate_mapping.py tests/test_mcp_config_consistency.py`锛沗Caliber path-trigger gate`锛堜粎 `pull_request`锛夛細`git fetch origin <base_ref>` 鍚庤繍琛?`python scripts/check_caliber_gate.py --base-ref origin/<base_ref>`锛孭R diff 瑙﹀強 `CALIBER_GATE_MAP` 涓殑 core_finance 鍙ｅ緞婧愭枃浠舵椂瀹氬悜杩愯瀵瑰簲 caliber 绾㈢嚎娴嬭瘯鏂囦欢锛堟槧灏勮〃鏉冨▉鍦ㄨ剼鏈唴锛屾嬁涓嶅埌 base-ref 鏃?fail-closed 闈為浂閫€鍑猴紱2026-08-12 璧峰叚涓?caliber 绾㈢嚎鏂囦欢鍚屾椂鏄?release suite 鏃犳潯浠舵垚鍛橈紝璺緞瑙﹀彂涓哄畾鍚戝揩鍙嶃€佸浠舵垚鍛樹负鏃犳潯浠跺厹搴曪紝浜掍负鍙屼繚闄╋級 |
| 鍏ㄩ噺鍏滃簳 | `backend-full-pytest` job锛堜粎 schedule / push鈫抦ain锛夛細`python -m pytest -q`锛屾敹闆?`tests/` + `backend/tests/` 鍏ㄩ儴娴嬭瘯 |

鎵ц鐜锛堣剼鏈敞鍏ワ紝鍐冲畾濂椾欢鐨勮瘉鏄庤竟鐣岋級锛?
- 涓存椂鐩綍闅旂锛歚MOSS_GOVERNANCE_PATH`銆乣MOSS_DUCKDB_PATH` 鎸囧悜涓€娆℃€?`moss-backend-release-*` 鐩綍
- `MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS=1`銆乣MOSS_SKIP_POSTGRES_MIGRATIONS=1`銆乣MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST=1`
- 鍗筹細濂椾欢璇佹槑 fixture 闅旂鐜涓嬬殑鍚堢害琛屼负锛屼笉璇佹槑杩佺Щ銆佺湡瀹炲瓨鍌ㄤ笌鐪熷疄閴存潈閾捐矾

CLI 琛ㄩ潰锛坄python scripts/backend_release_suite.py --help`锛夛細

| 鍙傛暟 | 鐢ㄩ€?|
| --- | --- |
| `--dry-run` | 鎵撳嵃濂椾欢鎵ц璁″垝 JSON锛堝惈 pytest 鍙傛暟涓庣幆澧冿級锛屾槸鍐嶇敓鎴愭湰娓呭崟鐨勪緷鎹?|
| `--mcp-profile fast\|full` | fast 涓?CI 榛樿锛沠ull 璺?`tests/test_project_mcp_servers.py`锛屼粎鍦ㄥ叡浜?MCP 琛屼负鍙樻洿鎴栧彂甯冩鏌ユ椂鎵嬪姩浣跨敤 |
| `--live-governance-dir` | 瀵规寚瀹氳繍琛屾椂娌荤悊鐩綍鍋氳缂樺璁★紝绌鸿緭鍏?fail-closed |
| `--governance-audit-output` | 瀹¤鎽樿杈撳嚭璺緞锛堥』涓?`--live-governance-dir` 鍚岀敤锛?|

## 2. 绗竴闃舵锛歚RELEASE_SUITE_TESTS`锛?0 涓枃浠讹紝鎸夎剼鏈『搴忥級

| # | 鏂囦欢 | 鍩?| 淇濇姢闈?|
| --- | --- | --- | --- |
| 1 | `tests/test_settings_contract.py` | 骞冲彴涓庨厤缃?| governance settings 榛樿鍊?/ 鐜鍙橀噺瑕嗙洊 / helper |
| 2 | `tests/test_health_endpoints.py` | 骞冲彴涓庨厤缃?| 鍋ュ悍妫€鏌ョ鐐?|
| 3 | `tests/test_positions_api_contract.py` | 涓氬姟 API 鍚堢害 | 鎸佷粨 API 灏佸 + 蹇収璇诲彇琛屼负 |
| 4 | `tests/test_pnl_api_contract.py` | 涓氬姟 API 鍚堢害 | PnL API 鍚堢害锛堝浠跺唴鏈€澶у崟鏂囦欢锛?|
| 5 | `tests/test_pnl_by_business_insights_contract.py` | 涓氬姟 API 鍚堢害 | 涓氬姟鏉＄嚎 PnL 娲炲療 |
| 6 | `tests/test_pnl_by_business_candidate_insights_contract.py` | 涓氬姟 API 鍚堢害 | 鍊欓€夊彛寰勶紙Scenario锛夋礊瀵?|
| 7 | `tests/test_candidate_period_comparison_contract_alignment.py` | 涓氬姟 API 鍚堢害 | 鍊欓€夋湡闂村姣斿悎绾︾増鏈法灞傚榻?|
| 8 | `tests/test_risk_tensor_api.py` | 涓氬姟 API 鍚堢害 | 椋庨櫓寮犻噺 API |
| 9 | `tests/test_balance_analysis_api.py` | 涓氬姟 API 鍚堢害 | 浣欓鍒嗘瀽 API |
| 10 | `tests/test_bond_analytics_api.py` | 涓氬姟 API 鍚堢害 | 鍊哄埜鍒嗘瀽 API 灏佸 + 鏍稿績缁撴灉瀛楁 |
| 11 | `tests/test_executive_dashboard_endpoints.py` | 涓氬姟 API 鍚堢害 | 楂樼浠〃鐩樼鐐?|
| 12 | `tests/test_cube_query_api.py` | 涓氬姟 API 鍚堢害 | cube 鏌ヨ API |
| 13 | `tests/test_liability_analytics_api.py` | 涓氬姟 API 鍚堢害 | 璐熷€哄垎鏋?API |
| 14 | `tests/test_liability_analytics_envelope_contract.py` | 涓氬姟 API 鍚堢害 | 璐熷€哄垎鏋愬搷搴斿皝濂?|
| 15 | `tests/test_result_meta_on_all_ui_endpoints.py` | 璺ㄧ鐐瑰皝濂?| 鎵€鏈?UI 绔偣 `result_meta` / `result` / `basis` 璇箟 |
| 16 | `tests/test_governance_lineage_audit.py` | 娌荤悊涓庤缂?| 琛€缂樺璁¤剼鏈涓猴紙鑴忚妫€娴嬨€佹棤鍓綔鐢級 |
| 17 | `tests/test_governance_doc_contract.py` | 娌荤悊涓庤缂?| 娌荤悊鏂囨。缁撴瀯涓庡唴瀹瑰悎绾?|
| 18 | `tests/test_golden_samples_capture_ready.py` | 榛勯噾鏍锋湰 | capture-ready 鏍锋湰瀛樺湪鎬?/ 鍏冩暟鎹?/ 瀛楁鍖归厤 / fail-closed 鍏佽娓呭崟 |
| 19 | `tests/test_ledger_pnl_net_interest_golden_sample.py` | 榛勯噾鏍锋湰 | 鍑€鍒╂伅榛勯噾鏍锋湰瀵硅处 + 鐢熶骇璁＄畻閾惧洖鏀?|
| 20 | `tests/test_executive_release_contract.py` | 榛勯噾鏍锋湰 | 鍙戝竷闂ㄦ牱鏈悎绾︼紙瀵瑰簲 `EXECUTIVE_RELEASE_SAMPLE_IDS`锛?|
| 21 | `tests/test_golden_sample_release_matrix.py` | 榛勯噾鏍锋湰 | 鏍锋湰鐩綍涓庡彂甯冮棬鏍锋湰 ID 瀵归綈锛涘畧鍗浠惰嚜韬繀椤诲寘鍚?exec 鍚堢害涓庢紓绉绘鏌?|
| 22 | `tests/test_live_route_page_contract_completeness.py` | 璺ㄧ鐐瑰皝濂?| 娲昏穬璺敱椤甸潰濂戠害瀹屽鎬?/ 鏄惧紡涓存椂璞佸厤锛堢鏍?+ burn-down锛?|
| 23 | `tests/test_backend_dependency_contract.py` | 骞冲彴涓庨厤缃?| 杩愯鏃朵緷璧栦笌 dev 渚濊禆鍒嗙 |
| 24 | `tests/test_no_finance_logic_in_frontend.py` | 鏋舵瀯杈圭晫 | 鍓嶇婧愮爜涓嶅緱鍚寮忛噾铻嶈绠?token |
| 25 | `tests/test_caliber_rule_fx_mid_conversion.py` | 鍙ｅ緞绾㈢嚎 | FX 涓棿浠锋姌绠楀彛寰?|
| 26 | `tests/test_caliber_rule_hat_mapping.py` | 鍙ｅ緞绾㈢嚎 | H/A/T 鏄犲皠鍙ｅ緞 |
| 27 | `tests/test_caliber_rule_subject_514_516_517_merge.py` | 鍙ｅ緞绾㈢嚎 | 514/516/517 绉戠洰鍚堝苟鍙ｅ緞 |
| 28 | `tests/test_caliber_rule_issuance_exclusion.py` | 鍙ｅ緞绾㈢嚎 | 鍙戣鍊烘帓闄ゅ彛寰?|
| 29 | `tests/test_caliber_rule_formal_scenario_gate.py` | 鍙ｅ緞绾㈢嚎 | Formal-Scenario 闂?|
| 30 | `tests/test_caliber_rule_accounting_basis.py` | 鍙ｅ緞绾㈢嚎 | 浼氳鍙ｅ緞褰掍竴 |

鍙戝竷闂ㄦ牱鏈?ID锛坄EXECUTIVE_RELEASE_SAMPLE_IDS`锛夛細`GS-EXEC-OVERVIEW-A`銆乣GS-EXEC-PNL-ATTR-A`銆乣GS-EXEC-SUMMARY-A`銆?
## 3. 绗簩闃舵锛氭不鐞?MCP 鍚堢害

| profile | 鏂囦欢 | pytest 鍙傛暟 | 浣跨敤鍦烘櫙 |
| --- | --- | --- | --- |
| fast锛堥粯璁わ紝CI 鍦ㄧ敤锛?| `tests/test_project_mcp_fast_contracts.py` | `-q -m mcp_fast` | PR / push 闂ㄧ锛涙湰鍦伴粯璁?MCP 鍙嶉鐜?|
| full锛堟墜鍔級 | `tests/test_project_mcp_servers.py` | `-q` | 鍏变韩 MCP 琛屼负鍙樻洿銆佸彂甯冩鏌ワ紙`--mcp-profile full`锛夛紱nightly 鍏ㄩ噺 pytest 涔熶細鏀堕泦 |

## 4. 鍐嶇敓鎴愭柟娉?
娓呭崟鍞竴鏉冨▉鏄剼鏈父閲忋€傛牳瀵?/ 鍐嶇敓鎴愭椂鎵ц锛?
```powershell
python scripts/backend_release_suite.py --dry-run
```

杈撳嚭 JSON 鐨?`pytest_args` 鍗崇涓€闃舵鏂囦欢搴忓垪锛宍governance_mcp_suite.pytest_args` 鍗崇浜岄樁娈碉紝`env` 鍗虫敞鍏ョ幆澧冦€傚皢鍏朵笌鏈枃妗?搂2/搂3 琛ㄦ牸閫愯姣斿锛堥『搴忎篃搴斾竴鑷达級銆?
## 5. 鏇存柊瑙勫垯

1. **鍚?PR 鍚屾**锛氫换浣曞鍒犳敼 `RELEASE_SUITE_TESTS`銆乣GOVERNANCE_MCP_*_SUITE_TESTS`銆乣EXECUTIVE_RELEASE_SAMPLE_IDS` 鐨?PR锛屽繀椤诲湪鍚屼竴 PR 鍐呮洿鏂版湰鏂囨。锛堣〃鏍艰 + 蹇収鏃ユ湡锛夛紝骞跺湪 PR 鎻忚堪娉ㄦ槑"濂椾欢鎴愬憳鍙樻洿"銆?2. **鍏ュ簱闂ㄦ**锛氭柊鏂囦欢鍔犲叆 release suite 搴旀弧瓒斥€斺€斿睘浜庡澶栧悎绾﹂潰 / 鍙戝竷闂ㄩ敋鐐癸紙鑰岄潪娣卞眰鍗曟祴锛夈€佽兘鍦ㄨ剼鏈敞鍏ョ殑闅旂鐜涓嬭繍琛屻€佹棤澶栭儴鏈嶅姟渚濊禆銆佽繍琛屾椂闂翠笌 `backend` job 20 鍒嗛挓闄愭椂鐩稿銆傛繁灞傚崟娴嬬殑 PR 闃叉姢璧?瑙﹁揪璺緞瀹氬悜娴嬭瘯"绾﹀畾锛堣 B0 鏂囨。 搂2锛夛紝涓嶈闈犳墿瀹?release suite 瑙ｅ喅銆?3. **绉婚櫎椤荤暀鐥?*锛氫粠濂椾欢绉婚櫎鏂囦欢鏃讹紝PR 鎻忚堪蹇呴』璇存槑璇ヤ繚鎶ら潰鐢变粈涔堟浛浠ｏ紙杩佺Щ鍒板埆鐨勬祴璇?/ 淇濇姢闈笅绾匡級銆?4. **閮ㄥ垎鎴愬憳璧勬牸鏈夋祴璇曞畧鍗?*锛歚tests/test_golden_sample_release_matrix.py` 浼氭柇瑷€濂椾欢鍖呭惈 exec 鍙戝竷鍚堢害涓庢紓绉绘鏌ユ枃浠垛€斺€斿姩杩欎簺鎴愬憳浼氱洿鎺ョ孩鐏紱浣嗗畠**涓嶅畧鍗湰鏂囨。**锛屾枃妗ｅ悓姝ラ潬鏈妭绾緥 + 涓嬫柟鏍￠獙鍛戒护銆?5. **涓€鑷存€ф牎楠?*锛堣瘎瀹?checklist 鍙洿鎺ュ紩鐢紱鑴氭湰涓庢枃妗ｄ换涓€婕傜Щ鍗抽潪闆堕€€鍑猴級锛?
```powershell
python -c "import pathlib, re, sys; sys.path.insert(0, '.'); import scripts.backend_release_suite as s; doc = pathlib.Path('docs/ci-release-suite.md').read_text(encoding='utf-8'); allowed = set(s.RELEASE_SUITE_TESTS) | set(s.GOVERNANCE_MCP_FAST_SUITE_TESTS) | set(s.GOVERNANCE_MCP_FULL_SUITE_TESTS) | {'tests/test_agent_eval_spec.py', 'tests/test_agent_eval_reward.py', 'tests/test_agent_eval_collect.py', 'tests/test_agent_eval_scoring_integrity.py', 'tests/test_agent_eval_replay.py', 'tests/test_agent_eval_pr_replay.py', 'tests/test_agent_eval_rollout.py', 'tests/test_agent_eval_coverage_report.py', 'tests/test_caliber_gate_mapping.py', 'tests/test_mcp_config_consistency.py'}; referenced = set(re.findall(r'tests/test_[a-z0-9_]+\.py', doc)); missing = sorted(set(s.RELEASE_SUITE_TESTS) - referenced); stale = sorted(referenced - allowed); assert not missing, ('doc missing suite files', missing); assert not stale, ('doc references non-suite files', stale); print('ok: %d suite files documented, no stale references' % len(s.RELEASE_SUITE_TESTS))"
```

璇勫 checklist 鏉℃锛堝彲璐磋繘璇勫瑙勭▼锛夛細

> 鍑?diff 瑙﹀強 `scripts/backend_release_suite.py` 鐨勫浠跺父閲忥細鏍稿 `docs/ci-release-suite.md` 鏄惁鍚?PR 鏇存柊锛屽苟杩愯涓婃柟涓€鑷存€ф牎楠屽懡浠わ紱鏂板鎴愬憳鏍稿鍏ュ簱闂ㄦ锛埪?.2锛夛紝绉婚櫎鎴愬憳鏍稿鐣欑棔璇存槑锛埪?.3锛夈€?