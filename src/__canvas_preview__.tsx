// @hyperide-preview-schema:fallback-props-v9
import React from 'react';

type InstanceEntry = { x?: number; y?: number; props?: Record<string, unknown> };
type PreviewComponent = React.ComponentType<Record<string, unknown>>;

function toPreviewComponent<P>(component: React.ComponentType<P>): PreviewComponent {
  return component as unknown as PreviewComponent;
}

import Chat from '..\frontend\src\pages\Chat';

const componentRegistry: Record<string, PreviewComponent> = {
  'frontend\src\pages\Chat.jsx': toPreviewComponent(Chat),
};

const sampleRenderMap: Record<string, React.FC> = {
};

const componentExportsMap: Record<string, string[]> = {
};

const sampleRenderersMap: Record<string, Record<string, React.FC>> = {
  'frontend\src\pages\Chat.jsx': {},
};

const callbackStubs = {
  onClick: () => console.log('[Preview] onClick'),
  onChange: (e: React.SyntheticEvent) => console.log('[Preview] onChange', (e?.target as HTMLInputElement)?.value),
  onSubmit: (e: React.SyntheticEvent) => { e?.preventDefault?.(); console.log('[Preview] onSubmit'); },
  onBlur: () => console.log('[Preview] onBlur'),
  onFocus: () => console.log('[Preview] onFocus'),
  onNavChange: (value: unknown) => console.log('[Preview] onNavChange', value),
  onNavigate: (value: unknown) => console.log('[Preview] onNavigate', value),
  onNext: () => console.log('[Preview] onNext'),
  onOpen: (value: unknown) => console.log('[Preview] onOpen', value),
  onClose: (value: unknown) => console.log('[Preview] onClose', value),
  onAddToCart: (...args: unknown[]) => console.log('[Preview] onAddToCart', args),
  onCreateEvent: () => console.log('[Preview] onCreateEvent'),
  onDateSelect: (value: unknown) => console.log('[Preview] onDateSelect', value),
  onFilterChange: (value: unknown) => console.log('[Preview] onFilterChange', value),
  onFiltersChange: (value: unknown) => console.log('[Preview] onFiltersChange', value),
  onPlayPause: () => console.log('[Preview] onPlayPause'),
  onPlayAll: () => console.log('[Preview] onPlayAll'),
  onPlaySong: (value: unknown) => console.log('[Preview] onPlaySong', value),
  onPrevious: () => console.log('[Preview] onPrevious'),
  onPress: (value: unknown) => console.log('[Preview] onPress', value),
  onQuickView: (value: unknown) => console.log('[Preview] onQuickView', value),
  onSearchChange: (value: unknown) => console.log('[Preview] onSearchChange', value),
  onSeek: (value: unknown) => console.log('[Preview] onSeek', value),
  onSectionChange: (value: unknown) => console.log('[Preview] onSectionChange', value),
  onSelect: (value: unknown) => console.log('[Preview] onSelect', value),
  onToggleCalendar: (value: unknown) => console.log('[Preview] onToggleCalendar', value),
  onVolumeChange: (value: unknown) => console.log('[Preview] onVolumeChange', value),
  onViewChange: (value: unknown) => console.log('[Preview] onViewChange', value),
};

const previewSong = {
  id: "preview-song",
  title: "Preview Song",
  artist: "Preview Artist",
  album: "Preview Album",
  duration: "3:24",
  durationSeconds: 204,
  coverUrl: "https://picsum.photos/seed/hyper-preview-song/96/96",
};

const previewPlaylist = {
  id: "preview-playlist",
  name: "Preview Playlist",
  description: "Preview playlist for isolated component rendering.",
  coverUrl: "https://picsum.photos/seed/hyper-preview-playlist/300/300",
  songs: [previewSong],
};

const previewFileItem = {
  id: "preview-folder",
  name: "Preview Folder",
  type: "folder",
  modified: "Today",
  owner: "Preview",
  starred: false,
  shared: false,
  parentId: null,
};

const previewLocation = { id: "preview-location", name: "Preview Location", address: "1 Preview St" };
const previewRideType = { id: "preview-ride", name: "Preview Ride", eta: 4, price: "$12.00" };
const previewTrip = {
  id: "preview-trip",
  pickup: previewLocation,
  destination: { ...previewLocation, id: "preview-destination", name: "Preview Destination" },
  rideType: previewRideType,
};

const previewListing = {
  id: "preview-listing",
  title: "Preview Stay",
  location: "Preview City",
  country: "Preview Country",
  distance: "1 km away",
  dates: "Apr 24-29",
  price: 120,
  currency: "USD",
  rating: 4.9,
  reviewCount: 12,
  images: ["#B7D5E8", "#D5E8B7"],
  isFavorite: false,
  isGuestFavorite: true,
  guests: 2,
  bedrooms: 1,
  beds: 1,
  baths: 1,
  description: "Preview listing description.",
  amenities: ["Wifi", "Kitchen"],
  host: { name: "Preview Host", avatar: "#82A8C4", isSuperhost: true, joinedDate: "2024" },
  reviews: [{ id: "preview-review", author: "Preview Guest", avatar: "#A8C482", date: "Today", rating: 5, comment: "Preview review." }],
  category: "Preview",
};

const previewProduct = {
  id: "1",
  name: "Preview Product",
  price: 29.99,
  originalPrice: 39.99,
  category: "sale",
  image: "#B7D5E8",
  rating: 4.5,
  reviewCount: 24,
  description: "Preview product description.",
  sizes: ["M"],
  colors: ["Blue"],
  brand: "Preview Brand",
  onSale: true,
};

const previewFilters = {
  search: "",
  status: "all",
  device: "all",
  country: "all",
  selectedBrands: [],
  selectedColor: null,
  priceRange: [0, 100],
};

const previewProject = {
  id: "preview-project",
  title: "Preview Project",
  description: "Preview project description.",
  tags: ["React", "TypeScript"],
  image: "#B7D5E8",
  url: "https://example.com",
};

const previewChartData = [
  { date: "Mon", pageViews: 1000, uniqueVisitors: 700, bounceRate: 32, avgSessionDuration: 180, conversions: 24, revenue: 1200 },
  { date: "Tue", pageViews: 1200, uniqueVisitors: 840, bounceRate: 30, avgSessionDuration: 190, conversions: 28, revenue: 1500 },
];

const previewData = previewChartData.map((row, index) => ({
  ...row,
  id: "preview-row-" + (index + 1),
  title: row.date,
  name: row.date,
  label: row.date,
  value: row.pageViews,
  status: "active",
  items: [],
  children: [],
}));

const previewWeatherDetails = {
  uvIndex: 4,
  uvLabel: "Moderate",
  windSpeed: 12,
  windDirection: "NW",
  humidity: 55,
  dewPoint: 8,
  pressure: 1013,
  visibility: 10,
};

const previewDate = new Date("2026-04-24T09:00:00Z");
const previewCalendars = [
  { type: "work", label: "Work", color: "#4285F4", enabled: true },
  { type: "personal", label: "Personal", color: "#0B8043", enabled: true },
  { type: "birthdays", label: "Birthdays", color: "#F4511E", enabled: true },
  { type: "holidays", label: "Holidays", color: "#F6BF26", enabled: true },
];

const _storeStubs: Record<string, unknown> = {};
const _stateStubs: Record<string, unknown> = {};
const previewFallbackProps: Record<string, unknown> = {
  ...callbackStubs,
  activeNav: "dashboard",
  activeSection: "dashboard",
  count: 1,
  chartData: previewChartData,
  calendars: previewCalendars,
  currentDate: previewDate,
  data: previewData,
  description: "Preview description",
  details: previewWeatherDetails,
  driver: { id: "preview-driver", name: "Preview Driver", rating: 4.9, vehicle: "Preview Car" },
  events: previewChartData,
  files: [previewFileItem],
  filters: previewFilters,
  headings: [],
  hours: previewChartData,
  index: 1,
  items: [],
  label: "Preview",
  listing: previewListing,
  listings: [previewListing],
  currentSongId: "preview-song",
  navigation: {
    navigate: (...args: unknown[]) => console.log('[Preview] navigation.navigate', args),
    goBack: () => console.log('[Preview] navigation.goBack'),
    back: () => console.log('[Preview] navigation.back'),
    push: (...args: unknown[]) => console.log('[Preview] navigation.push', args),
    popTo: (...args: unknown[]) => console.log('[Preview] navigation.popTo', args),
    reset: (value: unknown) => console.log('[Preview] navigation.reset', value),
    replace: (...args: unknown[]) => console.log('[Preview] navigation.replace', args),
    setOptions: (options: unknown) => console.log('[Preview] navigation.setOptions', options),
    dispatch: (action: unknown) => console.log('[Preview] navigation.dispatch', action),
  },
  path: [previewFileItem],
  playerState: { currentSong: previewSong, isPlaying: false, progress: 0.25, volume: 0.8 },
  playlist: previewPlaylist,
  playlists: [previewPlaylist],
  product: previewProduct,
  products: [previewProduct],
  project: previewProject,
  projects: [previewProject],
  rows: [],
  route: {
    key: "preview-route",
    name: "Preview",
    params: {
      id: "preview-id",
      activityId: "preview-activity",
      contactId: "preview-contact",
      conversationId: "preview-conversation",
      destination: { ...previewLocation, id: "preview-destination", name: "Preview Destination" },
      itemId: "preview-item",
      menuItemId: "preview-menu-item",
      pickup: previewLocation,
      restaurantId: "preview-restaurant",
      rideType: previewRideType,
      transactionId: "preview-transaction",
      trip: previewTrip,
    },
  },
  searchQuery: "",
  selectedDate: previewDate,
  song: previewSong,
  songs: [previewSong],
  tags: ["React", "TypeScript"],
  title: "Preview",
  value: "Preview",
  block: { id: "preview-block", type: "paragraph", content: "Preview block", checked: false },
  page: {
    id: "preview-page",
    title: "Preview Page",
    icon: "Preview",
    coverGradient: "linear-gradient(135deg, #4f46e5 0%, #06b6d4 100%)",
    parentId: null,
    isFavorite: false,
    lastEdited: "Preview",
    blocks: [{ id: "preview-block", type: "paragraph", content: "Preview block" }],
  },
  metric: { label: "Preview", value: "1,024", change: "+12%", trend: "up" },
  row: { id: "preview-row", name: "Preview row", status: "Done", priority: "Medium", date: "2026-01-01" },
  store: new Proxy({}, {
    get: (_target, prop) => {
      if (typeof prop !== 'string') return undefined;
      if (/^(?:set|toggle|on|add|remove|update|clear|reset|open|close)[A-Z]/.test(prop)) {
        return (_storeStubs[prop] ??= () => {});
      }
      if (['issues', 'items', 'rows', 'tags', 'users', 'comments', 'messages', 'notifications', 'cards', 'columns', 'tasks', 'lists', 'projects', 'labels', 'filters', 'priorities', 'statuses'].includes(prop)) return (_storeStubs[prop] ??= []);
      if (prop === 'issuesByStatus') return { backlog: [], todo: [], in_progress: [], done: [], cancelled: [] };
      if (prop === 'commandPaletteOpen' || prop === 'isOpen' || prop === 'isLoading' || prop === 'isError') return false;
      return undefined;
    },
  }),
  dispatch: () => {},
  reducer: () => {},
  state: new Proxy({}, {
    get: (_target, prop) => {
      if (typeof prop !== 'string') return undefined;
      if (/^(?:set|toggle|on|add|remove|update|clear|reset|open|close)[A-Z]/.test(prop)) {
        return (_stateStubs[prop] ??= () => {});
      }
      if (['issues', 'items', 'rows', 'tags', 'users', 'comments', 'messages', 'notifications', 'cards', 'columns', 'tasks', 'lists', 'projects', 'labels', 'filters', 'priorities', 'statuses'].includes(prop)) return (_stateStubs[prop] ??= []);
      if (prop === 'issuesByStatus') return { backlog: [], todo: [], in_progress: [], done: [], cancelled: [] };
      if (prop === 'commandPaletteOpen' || prop === 'isOpen' || prop === 'isLoading' || prop === 'isError') return false;
      return undefined;
    },
  }),
  theme: new Proxy({ colors: {}, spacing: {}, fontSizes: {}, shadows: {}, breakpoints: {} }, {
    get: (target, prop) => {
      if (typeof prop !== 'string') return undefined;
      if (prop in target) return (target as Record<string, unknown>)[prop];
      return {};
    },
  }),
  i18n: { t: (key: string) => key, language: 'en', changeLanguage: () => {} },
  session: { user: null, isAuthenticated: false, sessionId: 'preview-session' },
  auth: { user: null, isAuthenticated: false, sessionId: 'preview-session' },
  query: { data: undefined, isLoading: false, isError: false, error: null, refetch: () => {} },
  mutation: { mutate: () => {}, mutateAsync: async () => {}, isPending: false, isError: false },
  fetcher: { submit: () => {}, load: () => {}, data: undefined, state: 'idle' },
  intl: { formatMessage: (m: { defaultMessage?: string }) => m?.defaultMessage ?? '', locale: 'en' },
};

class ComponentErrorBoundary extends React.Component<
  { children: React.ReactNode; componentPath: string },
  { error: Error | null }
> {
  constructor(props: { children: React.ReactNode; componentPath: string }) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  componentDidCatch(error: Error) {
    window.parent.postMessage({
      type: 'hypercanvas:componentError',
      componentPath: this.props.componentPath,
      error: error.message,
    }, '*');
  }
  componentDidUpdate(prevProps: { componentPath: string }) {
    // Reset error state when switching to a different component
    if (prevProps.componentPath !== this.props.componentPath && this.state.error) {
      this.setState({ error: null });
    }
  }
  render() {
    if (this.state.error) {
      return null;
    }
    return this.props.children;
  }
}

function _ComponentSuccessSignal({ componentPath }: { componentPath: string }) {
  React.useEffect(() => {
    window.parent.postMessage({ type: 'hypercanvas:componentRenderSucceeded', componentPath }, '*');
  }, [componentPath]);
  return null;
}

function _ComponentMissingSignal({ componentPath }: { componentPath: string }) {
  React.useEffect(() => {
    window.parent.postMessage({ type: 'hypercanvas:componentMissing', componentPath }, '*');
  }, [componentPath]);
  return null;
}

interface CanvasPreviewProps {
  component?: string | null;
  mode?: 'single' | 'multi' | null;
}

export default function CanvasPreview({ component: componentProp, mode: modeProp }: CanvasPreviewProps = {}) {
  const [componentPath, setComponentPath] = React.useState<string | null>(componentProp ?? null);
  const [mode, setMode] = React.useState<'single' | 'multi'>(modeProp ?? 'single');

  // Sync props to state when parent re-renders with new searchParams (Next.js App Router)
  React.useEffect(() => {
    if (componentProp != null) setComponentPath(componentProp);
  }, [componentProp]);

  // Read URL params on client mount (Vite / CSR environments without prop injection)
  React.useEffect(() => {
    if (componentProp != null) return;
    const params = new URLSearchParams(window.location.search);
    const urlComponent = params.get('component');
    if (urlComponent) setComponentPath(urlComponent);
    const urlMode = params.get('mode');
    if (urlMode) setMode(urlMode as 'single' | 'multi');
  }, []);

  // Listen for component switches via postMessage (no iframe reload needed)
  React.useEffect(() => {
    function onMessage(e: MessageEvent) {
      if (e.data?.type === 'hypercanvas:setComponent' && e.data.component) {
        setComponentPath(e.data.component);
        // Sync URL so HMR full-reload / Fast Refresh remount picks up the current component
        try {
          const url = new URL(window.location.href);
          url.searchParams.set('component', e.data.component);
          window.history.replaceState(null, '', url.toString());
        } catch { /* ignore */ }
      }
    }
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, []);

  if (!componentPath) {
    return <div style={{ padding: 20, fontFamily: 'sans-serif' }}>
      <h2>Loading preview...</h2>
      <p>Waiting for component selection</p>
    </div>;
  }

  const Component = componentRegistry[componentPath];
  const sampleRenderers = sampleRenderersMap[componentPath] || {};

  if (mode !== 'multi') {
    const SampleDefault = sampleRenderMap[componentPath];
    if (!SampleDefault && !Component) {
      // Component not yet in the registry. Emit the missing signal so
      // extension.ts's recovery path runs `previewManager.ensureComponent`
      // and re-renders. Show a structured fallback instead of a bare
      // "Loading…" so the user can see the path/exports that were detected.
      const detectedExports = componentExportsMap[componentPath] ?? [];
      return (
        <div style={{ padding: 20, fontFamily: "sans-serif", color: "#666" }}>
          <_ComponentMissingSignal componentPath={componentPath} />
          <h2 style={{ margin: 0, fontSize: 16, color: "#333" }}>No sample for this component</h2>
          <p style={{ marginTop: 8 }}>{componentPath}</p>
          {detectedExports.length > 0 ? (
            <p style={{ marginTop: 8 }}>Detected exports: {detectedExports.join(", ")}</p>
          ) : (
            <p style={{ marginTop: 8 }}>Generating sample…</p>
          )}
        </div>
      );
    }
    return <ComponentErrorBoundary componentPath={componentPath}><div style={{ padding: 20 }}>{SampleDefault ? <SampleDefault /> : <Component {...previewFallbackProps} />}<_ComponentSuccessSignal componentPath={componentPath} /></div></ComponentErrorBoundary>;
  }

  const instances = ((window.parent as unknown) as { __CANVAS_INSTANCES__?: Record<string, InstanceEntry> }).__CANVAS_INSTANCES__ || {};

  return (
    <ComponentErrorBoundary componentPath={componentPath}>
    <div style={{ position: 'relative', width: 10000, height: 10000 }}>
      {Object.entries(instances).map(([id, instance]: [string, InstanceEntry]) => {
        const { x = 0, y = 0, props } = instance;

        if (props && Object.keys(props).length > 0 && Component) {
          const mergedProps = { ...previewFallbackProps, ...props };
          return (
            <div key={id} data-canvas-instance-id={id}
                 style={{ position: 'absolute', left: x, top: y }}>
              <Component {...mergedProps} />
            </div>
          );
        }

        const SampleComponent = sampleRenderers[id] || sampleRenderMap[componentPath];
        if (!SampleComponent) {
          if (Component) {
            return (
              <div key={id} data-canvas-instance-id={id}
                   style={{ position: 'absolute', left: x, top: y }}>
                <Component {...previewFallbackProps} />
              </div>
            );
          }
          return null;
        }

        return (
          <div key={id} data-canvas-instance-id={id}
               style={{ position: 'absolute', left: x, top: y }}>
            <SampleComponent />
          </div>
        );
      })}
      <_ComponentSuccessSignal componentPath={componentPath} />
    </div>
    </ComponentErrorBoundary>
  );
}

