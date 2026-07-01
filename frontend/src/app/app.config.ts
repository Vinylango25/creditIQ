import { APP_INITIALIZER, ApplicationConfig, provideBrowserGlobalErrorListeners, provideZoneChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { provideEchartsCore } from 'ngx-echarts';
import * as echarts from 'echarts/core';
import {
  BarChart, LineChart, PieChart, ScatterChart, RadarChart,
  HeatmapChart, BoxplotChart, CustomChart,
} from 'echarts/charts';
import {
  GridComponent, TooltipComponent, LegendComponent,
  TitleComponent, DataZoomComponent, VisualMapComponent,
  PolarComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

import { routes } from './app.routes';
import { ThemeService } from './core/theme.service';
import { ApiService } from './core/api.service';
import { StaticDataService } from './core/static-data.service';

echarts.use([
  BarChart, LineChart, PieChart, ScatterChart, RadarChart,
  HeatmapChart, BoxplotChart, CustomChart,
  GridComponent, TooltipComponent, LegendComponent,
  TitleComponent, DataZoomComponent, VisualMapComponent,
  PolarComponent,
  CanvasRenderer,
]);

function initTheme(theme: ThemeService) {
  return () => { /* ThemeService applies data-theme immediately */ };
}

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideHttpClient(),
    provideEchartsCore({ echarts }),
    // ── Serve all data from pre-built JSON assets (no backend needed) ────
    { provide: ApiService, useClass: StaticDataService },
    {
      provide:    APP_INITIALIZER,
      useFactory: initTheme,
      deps:       [ThemeService],
      multi:      true,
    },
  ],
};
