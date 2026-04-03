/**
 * ATLAS UI V12 - Browser Button Validation Test
 * ==============================================
 * Paste this entire script into the browser console (F12 → Console)
 * on the ATLAS Auto Studio page (http://localhost:9999/auto-studio)
 *
 * It will test ALL onclick/onchange handlers and report results.
 */

(function ATLAS_BUTTON_TEST() {
    console.clear();
    console.log('%c========================================', 'color: #8b5cf6; font-weight: bold');
    console.log('%c🧪 ATLAS V12 BUTTON VALIDATION TEST', 'color: #8b5cf6; font-weight: bold; font-size: 16px');
    console.log('%c========================================', 'color: #8b5cf6; font-weight: bold');

    // Collect all onclick and onchange handlers
    const elements = document.querySelectorAll('[onclick], [onchange]');
    const handlers = new Map();

    elements.forEach(el => {
        const onclick = el.getAttribute('onclick');
        const onchange = el.getAttribute('onchange');
        const attr = onclick || onchange;
        const type = onclick ? 'onclick' : 'onchange';

        // Extract function name
        const match = attr.match(/^([a-zA-Z_][a-zA-Z0-9_]*)\s*\(/);
        if (match) {
            const fnName = match[1];
            if (!handlers.has(fnName)) {
                handlers.set(fnName, { count: 0, type: type, elements: [] });
            }
            handlers.get(fnName).count++;
            handlers.get(fnName).elements.push(el);
        }
    });

    // Filter out false positives
    const falsePosivites = new Set(['if', 'confirm', 'alert', 'prompt', 'functionName']);
    falsePosivites.forEach(fp => handlers.delete(fp));

    // Test each handler
    const results = {
        working: [],
        broken: [],
        total: handlers.size
    };

    handlers.forEach((info, fnName) => {
        if (typeof window[fnName] === 'function') {
            results.working.push({ name: fnName, count: info.count, type: info.type });
        } else {
            results.broken.push({ name: fnName, count: info.count, type: info.type });
        }
    });

    // Report results
    console.log('\n%c📊 RESULTS:', 'color: #10b981; font-weight: bold; font-size: 14px');
    console.log(`   Total handlers: ${results.total}`);
    console.log(`   ✅ Working: ${results.working.length}`);
    console.log(`   ❌ Broken: ${results.broken.length}`);

    if (results.working.length > 0) {
        console.log('\n%c✅ WORKING HANDLERS:', 'color: #10b981; font-weight: bold');
        results.working.forEach(h => {
            console.log(`   ✓ ${h.name} (${h.type}, used ${h.count}x)`);
        });
    }

    if (results.broken.length > 0) {
        console.log('\n%c❌ BROKEN HANDLERS:', 'color: #ef4444; font-weight: bold');
        results.broken.forEach(h => {
            console.log(`   ✗ ${h.name} (${h.type}, used ${h.count}x)`);
        });

        // Show visual warning
        const chatArea = document.querySelector('.chat-messages, #chatMessages, [class*="chat"]');
        if (chatArea) {
            const warning = document.createElement('div');
            warning.innerHTML = `
                <div style="background:#dc2626;color:white;padding:16px;border-radius:8px;margin:12px 0;">
                    <strong style="font-size:14px;">🚨 BUTTON VALIDATION FAILED</strong><br><br>
                    <strong>${results.broken.length} handlers are BROKEN!</strong><br><br>
                    <code style="background:rgba(0,0,0,0.3);padding:8px;display:block;border-radius:4px;font-size:11px;white-space:pre-wrap;">${results.broken.map(h => `• ${h.name}`).join('\n')}</code>
                </div>
            `;
            chatArea.prepend(warning);
        }
    } else {
        console.log('\n%c🎉 ALL BUTTONS ARE WORKING!', 'color: #10b981; font-weight: bold; font-size: 16px');

        // Show success message
        const chatArea = document.querySelector('.chat-messages, #chatMessages, [class*="chat"]');
        if (chatArea) {
            const success = document.createElement('div');
            success.innerHTML = `
                <div style="background:#10b981;color:white;padding:16px;border-radius:8px;margin:12px 0;">
                    <strong style="font-size:14px;">✅ BUTTON VALIDATION PASSED</strong><br><br>
                    All <strong>${results.working.length}</strong> onclick/onchange handlers are properly exposed to window scope!
                </div>
            `;
            chatArea.prepend(success);
        }
    }

    // Critical functions check
    console.log('\n%c🔑 CRITICAL FUNCTION CHECK:', 'color: #f59e0b; font-weight: bold');
    const critical = [
        'handleScriptUpload', 'loadProject', 'saveProject',
        'approveStory', 'approveLocations', 'approveCharacters', 'approveCasting',
        'loadShotsReview', 'saveAllShotEdits', 'generateFirstFrames',
        'switchBibleTab', 'saveStoryBible', 'regenerateShotPlan'
    ];

    let criticalPass = 0;
    critical.forEach(fn => {
        if (typeof window[fn] === 'function') {
            console.log(`   ✅ ${fn}`);
            criticalPass++;
        } else {
            console.log(`   ❌ ${fn} - MISSING!`);
        }
    });

    console.log(`\n   Critical: ${criticalPass}/${critical.length} passed`);

    // Final summary
    console.log('\n%c========================================', 'color: #8b5cf6; font-weight: bold');
    const score = (results.working.length / results.total * 100).toFixed(1);
    if (results.broken.length === 0) {
        console.log(`%c🏆 VALIDATION SCORE: ${score}% - PERFECT!`, 'color: #10b981; font-weight: bold; font-size: 16px');
    } else {
        console.log(`%c⚠️ VALIDATION SCORE: ${score}% - NEEDS FIX`, 'color: #f59e0b; font-weight: bold; font-size: 16px');
    }
    console.log('%c========================================', 'color: #8b5cf6; font-weight: bold');

    // Return results for programmatic access
    window.__ATLAS_VALIDATION_RESULTS = results;
    return results;
})();
