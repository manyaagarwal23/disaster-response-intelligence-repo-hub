<?php

// Réception des SMS entrants — non-ASCII text before the class on purpose,
// to make sure byte offsets and string offsets are not confused.

namespace Ushahidi\DataSource\Twilio;

use Illuminate\Http\Request;

class TwilioController
{
    public function __construct(private DataSourceStorage $storage)
    {
    }

    public function handleRequest(Request $request)
    {
        $from = $request->input('From');
        $message = $request->input('Body');

        $this->storage->receive('twilio', 'sms', $from, $message);

        return response('', 200);
    }

    public static function make(): self
    {
        return new self(DataSourceStorage::instance());
    }
}
