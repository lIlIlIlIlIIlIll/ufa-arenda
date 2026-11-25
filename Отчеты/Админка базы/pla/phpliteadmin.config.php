<?php
// Конфигурация phpLiteAdmin для ИС «Аренда».
// База указывается явным путём (абсолютный путь надёжнее для встроенного сервера PHP).
$password = 'arenda';

$directory = false;
$subdirectories = false;

$db_path = '/Users/vlatt/Documents/deepseek-harness/default-workspace/ufa-arenda-db-admin/data/site.db';
$databases = array(
	array(
		'path' => $db_path,
		'name' => 'ИС Аренда (site.db)',
	),
);

$language = 'en';
$rowsNum = 50;
