# Data source flows

How incoming messages travel through the platform.

## Incoming SMS

An SMS provider such as Twilio calls a webhook. The controller reads
the sender and the message body and passes them to DataSourceStorage,
which saves a message that can later be turned into a post.

## Outgoing messages

Outgoing messages are queued and sent by a scheduled job.
