/**
 * ATLAS Studio Event Bridge (V16.7 Stub)
 * Provides cross-component event communication for the UI.
 */

export function attachStudioEventBridge() {
    const bridge = {
        listeners: new Map(),

        emit(eventType, data) {
            const event = new CustomEvent('auto-studio-event', {
                detail: { type: eventType, data, timestamp: Date.now() }
            });
            window.dispatchEvent(event);
            const handlers = this.listeners.get(eventType) || [];
            handlers.forEach(h => { try { h(data); } catch(e) { console.warn('[EventBridge]', e); } });
        },

        on(eventType, handler) {
            if (!this.listeners.has(eventType)) this.listeners.set(eventType, []);
            this.listeners.get(eventType).push(handler);
            return () => this.off(eventType, handler);
        },

        off(eventType, handler) {
            const handlers = this.listeners.get(eventType);
            if (handlers) {
                const idx = handlers.indexOf(handler);
                if (idx > -1) handlers.splice(idx, 1);
            }
        },

        projectLoaded(project) { this.emit('project-loaded', { project }); },
        castUpdated(castMap) { this.emit('cast-updated', { castMap }); },
        shotsUpdated(shots) { this.emit('shots-updated', { shots }); },
        bundleInvalidated(project) { this.emit('bundle-invalidated', { project }); }
    };

    console.log('[EventBridge] V16.7 attached');
    return bridge;
}

export default { attachStudioEventBridge };
