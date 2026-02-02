# Leaflet dark mode (invert-based)

Apply a CSS filter to map tiles so land and water both invert to a dark theme without hue issues.

## Usage

**Leaflet JS** — set `className` on the tile layer:

```js
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  className: 'map-tiles'
}).addTo(map);
```

**React-Leaflet** — pass `className` to `TileLayer`:

```tsx
<TileLayer
  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
  className="map-tiles"
/>
```

## CSS

```css
:root {
  --map-tiles-filter: brightness(0.6) invert(1) contrast(3) hue-rotate(200deg) saturate(0.3) brightness(0.7);
}

@media (prefers-color-scheme: dark) {
  .map-tiles {
    filter: var(--map-tiles-filter, none);
  }
}
```

- Light mode: tiles unchanged.
- Dark mode: invert + tune so land and water are both dark (no purple water / green land).

**Source:** [pkrasicki/issviewer](https://github.com/pkrasicki/issviewer), via [openstreetmap-website#2332](https://github.com/openstreetmap/openstreetmap-website/issues/2332).
