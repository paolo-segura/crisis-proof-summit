create table if not exists new_business_normal_email_log (
  id bigserial primary key,
  email text not null,
  email_number int not null,
  subject text not null,
  sent_at timestamptz not null default now(),
  message_id text,
  dry_run boolean not null default false,
  unique (email, email_number)
);

create index if not exists idx_bu_email_log_email on new_business_normal_email_log(email);
create index if not exists idx_bu_email_log_sent_at on new_business_normal_email_log(sent_at);
