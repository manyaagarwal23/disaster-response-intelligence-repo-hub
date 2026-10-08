<?php

$router->group(['prefix' => 'api/v5'], function () use ($router) {
    $router->get('/posts', 'PostController@index');
    $router->post('/posts', 'PostController@store');
    $router->put('/posts/{id}', 'PostController@update');
});
