-- MOSS:STMT
create table if not exists choice_news_event (
  event_key varchar,
  received_at varchar,
  group_id varchar,
  content_type varchar,
  serial_id bigint,
  request_id bigint,
  error_code bigint,
  error_msg varchar,
  topic_code varchar,
  item_index bigint,
  payload_text varchar,
  payload_json varchar
)
-- MOSS:STMT
alter table choice_news_event add column if not exists event_key varchar
