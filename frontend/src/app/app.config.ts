import { APP_INITIALIZER, ApplicationConfig, provideBrowserGlobalErrorListeners, provideZoneChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
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

echarts.use([
  BarChart, LineChart, PieChart, ScatterChart, RadarChart,
  HeatmapChart, BoxplotChart, CustomChart,
  GridComponent, TooltipComponent, LegendComponent,
  TitleComponent, DataZoomComponent, VisualMapComponent,
  PolarComponent,
  CanvasRenderer,
]);

function initTheme(theme: ThemeService) {
  return () => { /* ThemeService constructor + effect() applies data-theme immediately */ };
}

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideHttpClient(),   // no auth interceptor
    provideEchartsCore({ echarts }),
    {
      provide:    APP_INITIALIZER,
      useFactory: initTheme,
      deps:       [ThemeService],
      multi:      true,
    },
  ],
};
