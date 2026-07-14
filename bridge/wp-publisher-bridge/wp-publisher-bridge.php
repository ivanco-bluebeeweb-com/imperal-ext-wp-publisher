<?php
/**
 * Plugin Name:       WP Publisher Bridge
 * Plugin URI:        https://climtec.md
 * Description:       Открывает REST-доступ к SEO-полям Rank Math (title, description, focus keyword), чтобы приложение WP Publisher могло заполнять их при создании черновиков.
 * Version:           1.0.0
 * Requires at least: 6.0
 * Requires PHP:      8.0
 * Author:            Climtec
 * Author URI:        https://climtec.md
 * License:           GPL v2 or later
 * License URI:       https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain:       wp-publisher-bridge
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Регистрирует meta-поля Rank Math в REST API.
 *
 * Без этого WordPress игнорирует эти поля при создании поста через API,
 * и SEO-заголовок/описание остаются пустыми.
 */
function wp_publisher_bridge_register_meta() {
	$fields = array(
		'rank_math_title',
		'rank_math_description',
		'rank_math_focus_keyword',
	);

	foreach ( $fields as $key ) {
		register_post_meta(
			'post',
			$key,
			array(
				'show_in_rest'  => true,
				'single'        => true,
				'type'          => 'string',
				'auth_callback' => function () {
					return current_user_can( 'edit_posts' );
				},
			)
		);
	}
}
add_action( 'init', 'wp_publisher_bridge_register_meta' );
