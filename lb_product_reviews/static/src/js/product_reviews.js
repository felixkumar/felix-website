/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.LBProductReviews = publicWidget.Widget.extend({
    selector: '.lb-product-reviews',

    events: {
        'change .lb-review-sort': '_onSortChanged',
        'click .lb-load-more': '_onLoadMore',
        'click .lb-helpful': '_onHelpful',
    },

    start() {
        this.page = 1;
        this.sort = 'recent';
        this.loading = false;
        this._loadReviews(false);
        return this._super(...arguments);
    },

    async _loadReviews(append) {
        if (this.loading) return;
        this.loading = true;
        try {
            const result = await rpc('/lb_product_reviews/list', {
                product_id: parseInt(this.el.dataset.productId, 10),
                page: this.page,
                sort: this.sort,
            });
            if (result.error) return;
            this._renderSummary(result);
            const html = (result.items || []).map((item) => this._renderReview(item)).join('');
            const list = this.el.querySelector('.lb-review-list');
            if (!append) list.innerHTML = html || '<p class="text-muted">No reviews yet. Be the first to review this product!</p>';
            else list.insertAdjacentHTML('beforeend', html);
            const loaded = this.el.querySelectorAll('.lb-review-card').length;
            const more = this.el.querySelector('.lb-load-more');
            more.classList.toggle('d-none', loaded >= result.total || !result.items.length);
        } finally {
            this.loading = false;
        }
    },

    _renderSummary(result) {
        const avg = Number(result.average || 0);
        this.el.querySelector('.lb-average-rating').textContent = avg.toFixed(1);
        this.el.querySelector('.lb-total-reviews').textContent = result.total || 0;
        const stars = this.el.querySelector('.lb-stars');
        stars.textContent = '★'.repeat(Math.round(avg)) + '☆'.repeat(5 - Math.round(avg));
        for (let i = 1; i <= 5; i++) {
            const count = Number(result.counts?.[String(i)] || 0);
            const pct = result.total ? (count / result.total) * 100 : 0;
            const bar = this.el.querySelector(`.lb-rating-bar[data-rating="${i}"]`);
            const label = this.el.querySelector(`.lb-rating-count[data-rating="${i}"]`);
            if (bar) bar.style.width = `${pct}%`;
            if (label) label.textContent = count;
        }
    },

    _renderReview(item) {
        const stars = '★'.repeat(item.rating) + '☆'.repeat(5 - item.rating);
        const verified = item.verified ? '<span class="badge text-bg-success ms-2">✓ Verified Purchase</span>' : '';
        const safe = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
        return `<article class="lb-review-card border-bottom py-4" data-review-id="${item.id}">
            <div class="d-flex justify-content-between align-items-start">
                <div><strong>${safe(item.title)}</strong><div class="lb-small-stars">${stars}</div></div>
                <button type="button" class="btn btn-sm btn-link lb-helpful">Helpful (${item.helpful || 0})</button>
            </div>
            <div class="small text-muted mt-1">${safe(item.customer)} · ${safe(item.date)} ${verified}</div>
            <p class="mt-2 mb-0">${safe(item.review)}</p>
        </article>`;
    },

    _onSortChanged(ev) {
        this.sort = ev.currentTarget.value;
        this.page = 1;
        this._loadReviews(false);
    },

    _onLoadMore() {
        this.page += 1;
        this._loadReviews(true);
    },

    async _onHelpful(ev) {
        const button = ev.currentTarget;
        const card = button.closest('.lb-review-card');
        const id = parseInt(card.dataset.reviewId, 10);
        const result = await rpc(`/lb_product_reviews/helpful/${id}`, {});
        if (result?.helpful !== undefined) {
            button.textContent = `Helpful (${result.helpful})`;
            button.disabled = true;
        }
    },
});
