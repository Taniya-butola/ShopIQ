'use strict';

const API_BASE = '/api';

const api = {
  async get(path, params = {}) {
    const url = new URL(API_BASE + path, location.origin);
    Object.entries(params).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== '') {
        url.searchParams.set(key, value);
      }
    });

    const response = await fetch(url.toString());
    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: response.statusText }));
      throw new Error(err.error || 'Request failed');
    }
    return response.json();
  },

  async post(path, body) {
    const response = await fetch(API_BASE + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Request failed');
    return data;
  },

  search(params) {
    return this.get('/search', params);
  },

  suggest(query) {
    return this.get('/suggest', { q: query });
  },

  priceHistory(productId) {
    return this.get(`/product/${productId}/history`);
  },

  createAlert(body) {
    return this.post('/alerts', body);
  },
};

const state = {
  query: '',
  lastResults: null,
  historyChart: null,
};

const $ = (id) => document.getElementById(id);

const searchForm = $('searchForm');
const searchInput = $('searchInput');
const autocompleteList = $('autocompleteList');
const sortSelect = $('sortSelect');
const platformChecks = document.querySelectorAll('.platform-check');
const minPriceInput = $('minPrice');
const maxPriceInput = $('maxPrice');
const minRatingSelect = $('minRating');
const applyFiltersBtn = $('applyFilters');
const filtersBar = $('filtersBar');
const productsGrid = $('productsGrid');
const skeletons = $('skeletons');
const emptyState = $('emptyState');
const resultsStats = $('resultsStats');
const resultsCountEl = $('resultsCount');
const platformsOkEl = $('platformsOk');
const cacheStatusEl = $('cacheStatus');
const bestDealBanner = $('bestDealBanner');
const bdTitle = $('bdTitle');
const bdPrice = $('bdPrice');
const lowestPriceMetric = $('lowestPriceMetric');
const avgPriceMetric = $('avgPriceMetric');
const savingsMetric = $('savingsMetric');
const recommendationText = $('recommendationText');
const alertModal = $('alertModal');
const alertModalClose = $('alertModalClose');
const alertProductName = $('alertProductName');
const alertEmail = $('alertEmail');
const alertTargetPrice = $('alertTargetPrice');
const alertSubmit = $('alertSubmit');
const alertFeedback = $('alertFeedback');
const alertProductIdEl = $('alertProductId');
const historyModal = $('historyModal');
const historyModalClose = $('historyModalClose');
const historyProductName = $('historyProductName');
const historyEmpty = $('historyEmpty');
const toastContainer = $('toastContainer');

function showToast(message, type = 'info', duration = 3200) {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(8px)';
    toast.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
    setTimeout(() => toast.remove(), 220);
  }, duration);
}

function renderStars(rating) {
  if (!rating) return '<span class="stars">·····</span>';
  const filled = Math.round(rating);
  return `<span class="stars">${'★'.repeat(filled)}${'☆'.repeat(5 - filled)}</span>`;
}

function formatPrice(price) {
  if (price === null || price === undefined || Number.isNaN(price)) return '--';
  return '₹' + Number(price).toLocaleString('en-IN', { maximumFractionDigits: 0 });
}

function platformLabel(platform) {
  const labels = {
    shopping: 'Google Shopping',
    amazon: 'Amazon',
    flipkart: 'Flipkart',
    snapdeal: 'Snapdeal',
    demo: 'Demo',
  };
  return labels[platform] || platform;
}

function getPriceTone(product, comparison) {
  const price = Number(product.price || 0);
  if (!comparison.length || !price) {
    return { cardClass: 'price-mid', priceClass: 'mid', badgeClass: 'mid', label: 'Average deal' };
  }

  const { min, max, avg } = comparison;
  if (price === min) {
    return { cardClass: 'price-low', priceClass: 'low', badgeClass: 'low', label: 'Lowest price' };
  }

  const spread = Math.max(max - min, 1);
  if (price >= avg + spread * 0.2 || price === max) {
    return { cardClass: 'price-high', priceClass: 'high', badgeClass: 'high', label: 'Higher price' };
  }

  return { cardClass: 'price-mid', priceClass: 'mid', badgeClass: 'mid', label: 'Average deal' };
}

function escapeAttribute(value) {
  return String(value ?? '').replace(/"/g, '&quot;');
}

function renderCard(product, comparison, index) {
  const tone = getPriceTone(product, comparison);
  const card = document.createElement('article');
  card.className = `product-card ${tone.cardClass}${product.is_best_deal ? ' best-deal' : ''}`;
  card.style.animationDelay = `${index * 0.04}s`;

  const originalPriceHtml = product.original_price && product.original_price > product.price
    ? `<span class="card-original-price">${formatPrice(product.original_price)}</span>`
    : '';

  const discountHtml = product.discount_pct
    ? `<span class="card-discount">${Math.round(product.discount_pct)}% off</span>`
    : '';

  const ratingHtml = product.rating
    ? `${renderStars(product.rating)} <span>${product.rating.toFixed(1)}</span>${product.review_count ? `<span>${product.review_count.toLocaleString('en-IN')} reviews</span>` : ''}`
    : '<span>No ratings yet</span>';

  const deliveryHtml = product.delivery_info
    ? `<div class="card-delivery">${product.delivery_info}</div>`
    : '<div class="card-delivery">Delivery details not available</div>';

  const imageFallback = 'https://via.placeholder.com/320x320/F1F5F9/94A3B8?text=No+Image';

  card.innerHTML = `
    ${product.is_best_deal ? '<div class="best-deal-badge">Best deal</div>' : ''}
    <div class="price-rank-badge ${tone.badgeClass}">${tone.label}</div>
    <div class="card-image-wrap">
      <img
        src="${product.image_url || imageFallback}"
        alt="${escapeAttribute(product.title)}"
        loading="lazy"
        onerror="this.src='${imageFallback}'"
      />
    </div>
    <div class="card-body">
      <div class="card-topline">
        <span class="platform-badge">${platformLabel(product.platform)}</span>
        <span class="card-price-note">${product.is_best_deal ? 'Top pick' : 'Compare now'}</span>
      </div>
      <div class="card-title" title="${escapeAttribute(product.title)}">${product.title}</div>
      <div class="card-rating">${ratingHtml}</div>
      <div class="card-pricing">
        <span class="card-price ${tone.priceClass}">${formatPrice(product.price)}</span>
        ${originalPriceHtml}
        ${discountHtml}
      </div>
      ${deliveryHtml}
    </div>
    <div class="card-actions">
      <a
        href="${product.product_url || '#'}"
        target="_blank"
        rel="noopener noreferrer"
        class="btn-view"
        ${!product.product_url ? 'onclick="return false"' : ''}
      >View on ${platformLabel(product.platform)}</a>
      <button class="btn-icon" title="Set Price Alert" data-action="alert"
        data-id="${product.id}"
        data-name="${escapeAttribute(product.title)}"
        data-price="${product.price || 0}">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
          <path d="M13.73 21a2 2 0 01-3.46 0"></path>
        </svg>
      </button>
      <button class="btn-icon" title="Price History" data-action="history"
        data-id="${product.id}"
        data-name="${escapeAttribute(product.title)}">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
        </svg>
      </button>
    </div>
  `;

  return card;
}

function getSearchParams() {
  const checked = [...platformChecks]
    .filter((checkbox) => checkbox.checked)
    .map((checkbox) => checkbox.value);

  return {
    q: state.query,
    platforms: checked.join(',') || undefined,
    sort: sortSelect.value,
    min_price: minPriceInput.value || undefined,
    max_price: maxPriceInput.value || undefined,
    min_rating: minRatingSelect.value || undefined,
  };
}

function setLoading(isLoading) {
  const btnText = searchForm.querySelector('.btn-text');
  const btnSpinner = searchForm.querySelector('.btn-spinner');

  btnText.hidden = isLoading;
  btnSpinner.hidden = !isLoading;
  searchInput.disabled = isLoading;

  if (isLoading) {
    filtersBar.classList.remove('hidden');
    resultsStats.classList.add('hidden');
    bestDealBanner.classList.add('hidden');
    skeletons.classList.remove('hidden');
    emptyState.classList.add('hidden');
    productsGrid.innerHTML = '';
  } else {
    skeletons.classList.add('hidden');
  }
}

function buildComparison(products) {
  const prices = products
    .map((product) => Number(product.price))
    .filter((price) => Number.isFinite(price) && price > 0);

  if (!prices.length) return null;

  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const avg = prices.reduce((sum, price) => sum + price, 0) / prices.length;

  return {
    values: prices,
    min,
    max,
    avg,
    savings: max - min,
    length: prices.length,
  };
}

function renderResults(data, source) {
  const products = data.products || [];
  const comparison = buildComparison(products);

  productsGrid.innerHTML = '';
  emptyState.classList.add('hidden');
  resultsStats.classList.remove('hidden');

  resultsCountEl.textContent = `${data.total} offers compared`;
  platformsOkEl.textContent = (data.platforms_ok || []).length
    ? `Available on ${(data.platforms_ok || []).map((platform) => platformLabel(platform)).join(', ')}`
    : 'No platform responded';

  cacheStatusEl.textContent = source === 'cache'
    ? 'Showing cached comparison for faster review'
    : 'Showing fresh live comparison';

  if (comparison) {
    lowestPriceMetric.textContent = formatPrice(comparison.min);
    avgPriceMetric.textContent = formatPrice(comparison.avg);
    savingsMetric.textContent = formatPrice(comparison.savings);
  } else {
    lowestPriceMetric.textContent = '--';
    avgPriceMetric.textContent = '--';
    savingsMetric.textContent = '--';
  }

  const bestDeal = data.best_deal_id && products.find((product) => product.id === data.best_deal_id);
  if (bestDeal) {
    bdTitle.textContent = `${bestDeal.title} on ${platformLabel(bestDeal.platform)}`;
    bdPrice.textContent = formatPrice(bestDeal.price);
    recommendationText.textContent = `Best current pick is on ${platformLabel(bestDeal.platform)} with the lowest visible price.`;
    bestDealBanner.classList.remove('hidden');
  } else {
    recommendationText.textContent = 'Search results loaded. Review pricing, ratings, and delivery before buying.';
    bestDealBanner.classList.add('hidden');
  }

  if (!products.length) {
    emptyState.classList.remove('hidden');
    return;
  }

  const fragment = document.createDocumentFragment();
  products.forEach((product, index) => {
    fragment.appendChild(renderCard(product, comparison, index));
  });
  productsGrid.appendChild(fragment);

  filtersBar.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function runSearch() {
  const query = searchInput.value.trim();
  if (!query) return;

  state.query = query;
  autocompleteList.innerHTML = '';
  setLoading(true);

  try {
    const data = await api.search(getSearchParams());
    state.lastResults = data.data;
    renderResults(data.data, data.source);
  } catch (error) {
    showToast(`Search failed: ${error.message}`, 'error');
    emptyState.classList.remove('hidden');
  } finally {
    setLoading(false);
  }
}

function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

const fetchSuggestions = debounce(async (query) => {
  if (query.length < 2) {
    autocompleteList.innerHTML = '';
    return;
  }

  try {
    const data = await api.suggest(query);
    const suggestions = data.data || [];
    autocompleteList.innerHTML = '';
    suggestions.forEach((suggestion) => {
      const item = document.createElement('li');
      item.textContent = suggestion;
      item.addEventListener('click', () => {
        searchInput.value = suggestion;
        autocompleteList.innerHTML = '';
        runSearch();
      });
      autocompleteList.appendChild(item);
    });
  } catch {
    autocompleteList.innerHTML = '';
  }
}, 250);

function openAlertModal(productId, productName, currentPrice) {
  alertProductIdEl.value = productId;
  alertProductName.textContent = productName;
  alertTargetPrice.value = currentPrice ? Math.round(currentPrice * 0.95) : '';
  alertFeedback.textContent = '';
  alertFeedback.className = 'form-feedback';
  alertModal.classList.remove('hidden');
  alertEmail.focus();
}

alertModalClose.addEventListener('click', () => alertModal.classList.add('hidden'));
alertModal.addEventListener('click', (event) => {
  if (event.target === alertModal) alertModal.classList.add('hidden');
});

alertSubmit.addEventListener('click', async () => {
  const email = alertEmail.value.trim();
  const targetPrice = parseFloat(alertTargetPrice.value);
  const productName = alertProductName.textContent;

  if (!email || !email.includes('@')) {
    alertFeedback.textContent = 'Please enter a valid email address.';
    alertFeedback.className = 'form-feedback error';
    return;
  }

  if (!targetPrice || targetPrice <= 0) {
    alertFeedback.textContent = 'Please enter a valid target price.';
    alertFeedback.className = 'form-feedback error';
    return;
  }

  alertSubmit.textContent = 'Creating alert...';
  alertSubmit.disabled = true;

  try {
    await api.createAlert({
      email,
      product_id: alertProductIdEl.value,
      product_name: productName,
      target_price: targetPrice,
    });
    alertFeedback.textContent = `Alert created for ${email}.`;
    alertFeedback.className = 'form-feedback success';
    showToast('Price alert created', 'success');
    setTimeout(() => alertModal.classList.add('hidden'), 1200);
  } catch (error) {
    alertFeedback.textContent = `Failed: ${error.message}`;
    alertFeedback.className = 'form-feedback error';
  } finally {
    alertSubmit.textContent = 'Create alert';
    alertSubmit.disabled = false;
  }
});

async function openHistoryModal(productId, productName) {
  historyProductName.textContent = productName;
  historyEmpty.classList.add('hidden');
  historyModal.classList.remove('hidden');

  if (state.historyChart) {
    state.historyChart.destroy();
    state.historyChart = null;
  }

  try {
    const data = await api.priceHistory(productId);
    const history = data.data || [];

    if (!history.length) {
      historyEmpty.classList.remove('hidden');
      return;
    }

    const labels = history.map((row) =>
      new Date(row.recorded_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
    );
    const prices = history.map((row) => row.price);

    const ctx = $('historyChart').getContext('2d');
    state.historyChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Price (INR)',
          data: prices,
          borderColor: '#2563EB',
          backgroundColor: 'rgba(37, 99, 235, 0.10)',
          borderWidth: 3,
          pointBackgroundColor: '#2563EB',
          pointBorderColor: '#ffffff',
          pointBorderWidth: 2,
          pointRadius: 4,
          fill: true,
          tension: 0.35,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (context) => formatPrice(context.raw),
            },
          },
        },
        scales: {
          x: {
            ticks: { color: '#64748B' },
            grid: { color: 'rgba(148, 163, 184, 0.18)' },
          },
          y: {
            ticks: {
              color: '#64748B',
              callback: (value) => formatPrice(value),
            },
            grid: { color: 'rgba(148, 163, 184, 0.18)' },
          },
        },
      },
    });
  } catch {
    historyEmpty.classList.remove('hidden');
  }
}

historyModalClose.addEventListener('click', () => historyModal.classList.add('hidden'));
historyModal.addEventListener('click', (event) => {
  if (event.target === historyModal) historyModal.classList.add('hidden');
});

productsGrid.addEventListener('click', (event) => {
  const button = event.target.closest('[data-action]');
  if (!button) return;

  const { action, id, name, price } = button.dataset;

  if (action === 'alert') {
    openAlertModal(id, name, parseFloat(price));
  }

  if (action === 'history') {
    openHistoryModal(id, name);
  }
});

searchForm.addEventListener('submit', (event) => {
  event.preventDefault();
  runSearch();
});

searchInput.addEventListener('input', (event) => {
  fetchSuggestions(event.target.value.trim());
});

document.addEventListener('click', (event) => {
  if (!event.target.closest('.search-box')) autocompleteList.innerHTML = '';
});

document.querySelectorAll('.tag').forEach((tag) => {
  tag.addEventListener('click', () => {
    searchInput.value = tag.dataset.q;
    runSearch();
  });
});

applyFiltersBtn.addEventListener('click', () => {
  if (state.query) runSearch();
});

sortSelect.addEventListener('change', () => {
  if (state.query) runSearch();
});

document.addEventListener('keydown', (event) => {
  if (event.key === '/' && document.activeElement !== searchInput) {
    event.preventDefault();
    searchInput.focus();
  }

  if (event.key === 'Escape') {
    alertModal.classList.add('hidden');
    historyModal.classList.add('hidden');
  }
});

$('alertsNavBtn').addEventListener('click', (event) => {
  event.preventDefault();
  const email = prompt('Enter your email to view alerts:');
  if (!email) return;

  api.get('/alerts', { email })
    .then((data) => {
      const alerts = data.data || [];
      if (!alerts.length) {
        showToast(`No alerts found for ${email}`, 'info');
        return;
      }

      const lines = alerts.map((alert) => `• ${alert.product_name} at ${formatPrice(alert.target_price)}`);
      alert(`Your SHOPIQ alerts (${alerts.length})\n\n${lines.join('\n')}`);
    })
    .catch(() => showToast('Could not load alerts', 'error'));
});
