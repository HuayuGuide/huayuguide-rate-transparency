<?php
/**
 * HuayuGuide Rate Transparency (public repo reader)
 *
 * Shortcodes:
 * - [hg_usdt_rate pair="USDT/CNY"]
 * - [hg_usdt_rate_table]
 */

if (!defined('ABSPATH')) {
    exit;
}

if (!defined('HG_RATE_TRANSPARENCY_RAW_BASE')) {
    define('HG_RATE_TRANSPARENCY_RAW_BASE', 'https://raw.githubusercontent.com/HuayuGuide/huayuguide-rate-transparency/main/data/latest');
}

if (!function_exists('hg_rate_transparency_fetch_snapshot')) {
    function hg_rate_transparency_fetch_snapshot(string $pair = 'USDT/CNY'): ?array {
        $pair = strtoupper(trim($pair));
        $parts = explode('/', $pair);
        if (count($parts) !== 2) {
            return null;
        }
        $base = trim($parts[0]);
        $quote = trim($parts[1]);
        if ($base !== 'USDT') {
            return null;
        }

        $file = 'usdt_' . strtolower($quote) . '.json';
        $url = rtrim(HG_RATE_TRANSPARENCY_RAW_BASE, '/') . '/' . $file;
        $cache_key = 'hg_rt_' . md5($url);

        $cached = get_transient($cache_key);
        if (is_array($cached) && !empty($cached['pair'])) {
            return $cached;
        }

        $resp = wp_remote_get($url, [
            'timeout' => 3,
            'redirection' => 2,
            'user-agent' => 'HuayuGuideRateReader/1.0',
        ]);

        if (is_wp_error($resp)) {
            return null;
        }

        $body = wp_remote_retrieve_body($resp);
        $data = json_decode($body, true);
        if (!is_array($data) || empty($data['pair']) || !isset($data['bid']) || !isset($data['ask'])) {
            return null;
        }

        set_transient($cache_key, $data, 30 * MINUTE_IN_SECONDS);
        return $data;
    }
}

if (!function_exists('hg_rate_transparency_format_snapshot')) {
    function hg_rate_transparency_format_snapshot(array $snap): string {
        $pair = esc_html((string) ($snap['pair'] ?? 'USDT/CNY'));
        $bid = number_format((float) ($snap['bid'] ?? 0), 4);
        $ask = number_format((float) ($snap['ask'] ?? 0), 4);
        $mid = number_format((float) ($snap['mid'] ?? 0), 4);
        $quality = number_format((float) ($snap['quality_score'] ?? 0), 1);
        $source = esc_html((string) ($snap['source'] ?? 'unknown'));
        $asof = esc_html((string) ($snap['asof_iso'] ?? 'n/a'));

        return '<div class="hg-rate-card" style="display:inline-block;padding:10px 12px;border:1px solid #d9e1ef;border-radius:10px;background:#f8fbff;color:#1e293b;line-height:1.6;">'
            . '<div><strong>' . $pair . '</strong> 参考价</div>'
            . '<div>Bid（卖U参考）: <strong>' . $bid . '</strong></div>'
            . '<div>Ask（买U参考）: <strong>' . $ask . '</strong></div>'
            . '<div>Mid: ' . $mid . ' | 质量分: ' . $quality . '</div>'
            . '<div style="font-size:12px;color:#64748b;">源: ' . $source . ' | asof: ' . $asof . '</div>'
            . '</div>';
    }
}

if (!function_exists('hg_usdt_rate_shortcode')) {
    function hg_usdt_rate_shortcode(array $atts): string {
        $atts = shortcode_atts([
            'pair' => 'USDT/CNY',
        ], $atts, 'hg_usdt_rate');

        $snap = hg_rate_transparency_fetch_snapshot((string) $atts['pair']);
        if (!$snap) {
            return '<span style="color:#64748b;">汇率快照暂不可用</span>';
        }
        return hg_rate_transparency_format_snapshot($snap);
    }
    add_shortcode('hg_usdt_rate', 'hg_usdt_rate_shortcode');
}

if (!function_exists('hg_usdt_rate_table_shortcode')) {
    function hg_usdt_rate_table_shortcode(array $atts): string {
        unset($atts);
        $pairs = ['USDT/CNY', 'USDT/HKD', 'USDT/PHP'];
        $rows = [];

        foreach ($pairs as $pair) {
            $snap = hg_rate_transparency_fetch_snapshot($pair);
            if (!$snap) {
                continue;
            }
            $rows[] = '<tr>'
                . '<td style="padding:8px 10px;">' . esc_html($pair) . '</td>'
                . '<td style="padding:8px 10px;">' . number_format((float) ($snap['bid'] ?? 0), 4) . '</td>'
                . '<td style="padding:8px 10px;">' . number_format((float) ($snap['ask'] ?? 0), 4) . '</td>'
                . '<td style="padding:8px 10px;">' . number_format((float) ($snap['quality_score'] ?? 0), 1) . '</td>'
                . '<td style="padding:8px 10px;">' . esc_html((string) ($snap['source'] ?? 'unknown')) . '</td>'
                . '</tr>';
        }

        if (empty($rows)) {
            return '<span style="color:#64748b;">汇率快照暂不可用</span>';
        }

        return '<table style="border-collapse:collapse;border:1px solid #d9e1ef;border-radius:10px;overflow:hidden;">'
            . '<thead><tr style="background:#f1f5f9;">'
            . '<th style="padding:8px 10px;text-align:left;">Pair</th>'
            . '<th style="padding:8px 10px;text-align:left;">Bid</th>'
            . '<th style="padding:8px 10px;text-align:left;">Ask</th>'
            . '<th style="padding:8px 10px;text-align:left;">质量分</th>'
            . '<th style="padding:8px 10px;text-align:left;">来源</th>'
            . '</tr></thead>'
            . '<tbody>' . implode('', $rows) . '</tbody>'
            . '</table>';
    }
    add_shortcode('hg_usdt_rate_table', 'hg_usdt_rate_table_shortcode');
}
