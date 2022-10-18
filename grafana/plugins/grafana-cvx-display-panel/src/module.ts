import { MetricsPanelCtrl } from 'grafana/app/plugins/sdk';
import defaultsDeep from 'lodash/defaultsDeep';
import Hls from 'hls.js';

export default class CVXDisplay extends MetricsPanelCtrl {
  static templateUrl = 'partials/module.html';

  panelDefaults = {
    videoUrlField: '',
    videoUrl: '',
  };

  /** @ngInject */
  constructor($scope, $injector) {
    super($scope, $injector);
    defaultsDeep(this.panel, this.panelDefaults);

    this.events.on('init-edit-mode', this.onInitEditMode.bind(this));
    this.events.on('render', this.onRender.bind(this));
    this.events.on('data-error', this.onDataError.bind(this));
    this.events.on('panel-initialized', this.render.bind(this));
    this.events.on('component-did-mount', this.render.bind(this));
  }

  onInitEditMode() {
    this.addEditorTab('Options', `public/plugins/${this.pluginId}/partials/options.html`, 2);
  }

  renderVideo(videoUrl) {
    const hls = new Hls();
    const video = document.getElementById('ng-cvx-display-video') as HTMLVideoElement;

    this.panel.videoUrl = videoUrl;

    hls.loadSource(videoUrl);
    hls.attachMedia(video);

    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      video.play();
    });
  }

  onRender() {
    const { videoUrlField } = this.panel;
    console.log(this);
    if (!videoUrlField) {
      fetch(window.location.protocol + '//' + window.location.host + '/display/api/streams')
        .then((res) => res.json())
        .then((res) => {
          this.renderVideo(res.list[0]);
        });
    } else {
      this.renderVideo(videoUrlField);
    }

    this.renderingCompleted();
  }

  onDataError(err: any) {
    console.log('onDataError', err);
  }
}

export { CVXDisplay as PanelCtrl };
