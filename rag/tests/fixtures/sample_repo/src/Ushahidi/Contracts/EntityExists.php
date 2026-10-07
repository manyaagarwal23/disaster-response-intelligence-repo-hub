<?php

namespace Ushahidi\Contracts;

interface EntityExists
{
    /**
     * Check whether an entity with the given id exists.
     */
    public function exists(int $id): bool;
}
