# exec-01-nested-composer-unpinned

A PHP project whose root `composer.json` pins PHP with `require.php`. A nested Composer project,
`tools/lint/composer.json`, names no `php` key, and no `.php-version` sits in its folder or a parent folder.
Run the command below from each project's folder.

## Development

```bash
composer install
```
