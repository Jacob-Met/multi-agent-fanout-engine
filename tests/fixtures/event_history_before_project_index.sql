-- Native predecessor fixture: 6303882e1a4a45f5952c98cdae362b869c0f11b1.
-- Generated with Plan and Ledger transitions before project-event indexing.
BEGIN TRANSACTION;
CREATE TABLE events(
                seq INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
                part_id TEXT, event TEXT NOT NULL, detail_json TEXT NOT NULL, at REAL NOT NULL);
INSERT INTO "events" VALUES(1,'legacy-project',NULL,'plan_recorded','{"part_count":3,"plan_digest":"3cd413704509b9f908a520d441f7de43d587a7c625429c62efa48741d95298c4"}',1791843882.3018599);
INSERT INTO "events" VALUES(2,'legacy-project','done','dispatch_started','{"route":{"effort":"low","model":"fixture-model"},"worker_id":"legacy-worker"}',1791843882.3019552);
INSERT INTO "events" VALUES(3,'legacy-project','done','dispatch_accepted','{"task_id":"accepted-完成"}',1791843882.3020005);
INSERT INTO "events" VALUES(4,'other-project',NULL,'plan_recorded','{"part_count":1,"plan_digest":"ea78e3af47b1730b50046f33bb6a939354d41e253017dc0e6c2520dd462e954b"}',1791843882.3020535);
INSERT INTO "events" VALUES(5,'legacy-project','done','completed','{"artifact_ref":"fixture:completed-result","evidence":{"finding":"Synthetic retained transition; no external work was submitted.","locator":"fixture:done","source":"authored legacy fixture"}}',1791843882.3021011);
INSERT INTO "events" VALUES(6,'legacy-project','unknown','dispatch_started','{"route":{"effort":"low","model":"fixture-model"},"worker_id":"legacy-worker"}',1791843882.3021317);
INSERT INTO "events" VALUES(7,'legacy-project','unknown','dispatch_accepted','{"task_id":"accepted-α"}',1791843882.3021965);
INSERT INTO "events" VALUES(8,'legacy-project','unknown','outcome_unknown','{"finding":"Synthetic retained transition; no external work was submitted.","locator":"fixture:unknown","source":"authored legacy fixture"}',1791843882.3022454);
INSERT INTO "events" VALUES(9,'other-project','other','dispatch_started','{"route":{"effort":"low","model":"fixture-model"},"worker_id":"neighbor-worker"}',1791843882.3022792);
INSERT INTO "events" VALUES(10,'other-project','other','dispatch_accepted','{"task_id":"neighbor-task"}',1791843882.3023007);
INSERT INTO "events" VALUES(11,'other-project','other','outcome_unknown','{"finding":"Synthetic retained transition; no external work was submitted.","locator":"fixture:other","source":"authored legacy fixture"}',1791843882.30233);
INSERT INTO "events" VALUES(12,'other-project','other','reconciled','{"artifact_ref":null,"evidence":{"finding":"Synthetic retained transition; no external work was submitted.","locator":"fixture:other-failed","source":"authored legacy fixture"},"verdict":"failed"}',1791843882.3023725);
CREATE TABLE parts(
                project_id TEXT NOT NULL, part_id TEXT NOT NULL, payload_json TEXT NOT NULL,
                payload_digest TEXT NOT NULL, idempotency_key TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('queued','dispatching','running','outcome_unknown','completed','failed')),
                worker_id TEXT, task_id TEXT, route_json TEXT, artifact_ref TEXT,
                evidence_json TEXT, updated_at REAL NOT NULL,
                PRIMARY KEY(project_id,part_id),
                FOREIGN KEY(project_id) REFERENCES projects(project_id));
INSERT INTO "parts" VALUES('legacy-project','done','{"depends_on":[],"id":"done","instruction":"Keep the authored completed result.","tags":["reading","reading"]}','3cd413704509b9f908a520d441f7de43d587a7c625429c62efa48741d95298c4','fanout-47d7bc27f907959120a6109289eeeca43f245532b22c0f0905611b2946d7b34f','completed','legacy-worker','accepted-完成','{"effort":"low","model":"fixture-model"}','fixture:completed-result','{"finding":"Synthetic retained transition; no external work was submitted.","locator":"fixture:done","source":"authored legacy fixture"}',1791843882.3020785);
INSERT INTO "parts" VALUES('legacy-project','unknown','{"depends_on":[],"id":"unknown","instruction":"Retain an unresolved accepted result.","tags":[]}','3cd413704509b9f908a520d441f7de43d587a7c625429c62efa48741d95298c4','fanout-1c37284a114b729cd516b38daf0a6dc04f382c763780deab7f15001ec23e4b2c','outcome_unknown','legacy-worker','accepted-α','{"effort":"low","model":"fixture-model"}',NULL,'{"finding":"Synthetic retained transition; no external work was submitted.","locator":"fixture:unknown","source":"authored legacy fixture"}',1791843882.3022206);
INSERT INTO "parts" VALUES('legacy-project','waiting','{"depends_on":["unknown"],"id":"waiting","instruction":"Wait for verified unknown work.","tags":[]}','3cd413704509b9f908a520d441f7de43d587a7c625429c62efa48741d95298c4','fanout-c2ef2661682d2b73309953381c8b88108f12663369f15a120483f6aecfa5c718','queued',NULL,NULL,NULL,NULL,NULL,1791843882.3018491);
INSERT INTO "parts" VALUES('other-project','other','{"depends_on":[],"id":"other","instruction":"Retain a separate failed result.","tags":[]}','ea78e3af47b1730b50046f33bb6a939354d41e253017dc0e6c2520dd462e954b','fanout-53045f2e487135a35d7e79142e19049dffaabf16d4df80290692728ee59dfd3c','failed','neighbor-worker','neighbor-task','{"effort":"low","model":"fixture-model"}',NULL,'{"finding":"Synthetic retained transition; no external work was submitted.","locator":"fixture:other-failed","source":"authored legacy fixture"}',1791843882.3023493);
CREATE TABLE projects(
                project_id TEXT PRIMARY KEY, plan_digest TEXT NOT NULL, plan_json TEXT NOT NULL);
INSERT INTO "projects" VALUES('legacy-project','3cd413704509b9f908a520d441f7de43d587a7c625429c62efa48741d95298c4','{"parts":[{"depends_on":[],"id":"done","instruction":"Keep the authored completed result.","tags":["reading","reading"]},{"depends_on":[],"id":"unknown","instruction":"Retain an unresolved accepted result.","tags":[]},{"depends_on":["unknown"],"id":"waiting","instruction":"Wait for verified unknown work.","tags":[]}],"project":"legacy-project"}');
INSERT INTO "projects" VALUES('other-project','ea78e3af47b1730b50046f33bb6a939354d41e253017dc0e6c2520dd462e954b','{"parts":[{"depends_on":[],"id":"other","instruction":"Retain a separate failed result.","tags":[]}],"project":"other-project"}');
DELETE FROM "sqlite_sequence";
INSERT INTO "sqlite_sequence" VALUES('events',12);
COMMIT;
