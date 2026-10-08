<?php

namespace Ushahidi\Core\Usecase\Concerns;

use Ushahidi\Contracts\Entity;
use Ushahidi\Core\Exception\NotFoundException;

trait VerifyEntityLoaded
{
    abstract protected function getResourceName();

    protected function verifyEntityLoaded(Entity $entity, $lookup)
    {
        if (!$entity->getId()) {
            throw new NotFoundException(sprintf(
                'Could not locate any %s matching [%s]',
                $entity->getResource(),
                $lookup
            ));
        }

        return $entity;
    }
}
