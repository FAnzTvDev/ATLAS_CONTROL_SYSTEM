#!/usr/bin/env python3
"""
BFP Safety Agent (Phase C)
--------------------------
Simulates BFP Safety Runtime behavior under adversarial 'Swarm' harassment.
Monitors Shield, Fade, and Exit triggers at a 10Hz tick rate.
"""

import time
import random
import argparse
import sys
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Optional

class TriggerState(Enum):
    ARMED = auto()
    ACTIVE = auto()
    TRIGGERED = auto()
    FAILED = auto()

@dataclass
class SwarmPacket:
    timestamp: float
    intensity: float  # 0.0 to 1.0
    payload: str

@dataclass
class RuntimeState:
    health: float = 100.0
    stress: float = 0.0
    shield_status: TriggerState = TriggerState.ARMED
    fade_status: TriggerState = TriggerState.ARMED
    exit_status: TriggerState = TriggerState.ARMED
    dropped_frames: int = 0
    tick_count: int = 0

class BFPSafetyRuntime:
    def __init__(self, tick_rate_hz: int = 10):
        self.tick_rate = tick_rate_hz
        self.tick_interval = 1.0 / tick_rate_hz
        self.state = RuntimeState()
        
        # BFP Safety Levels
        self.LEVEL_1_SHIELD = 40.0
        self.LEVEL_2_FADE = 70.0
        self.LEVEL_4_EXIT = 90.0
        
        self.thresholds = {
            "shield": self.LEVEL_1_SHIELD,
            "fade": self.LEVEL_2_FADE,
            "exit": self.LEVEL_4_EXIT
        }
    
    def process_swarm_packet(self, packet: SwarmPacket):
        """Ingest adversarial packet and update stress metrics."""
        impact = packet.intensity * 5.0
        self.state.stress = min(100.0, self.state.stress + impact)
        self.state.health = max(0.0, self.state.health - (impact * 0.1))
        
        # Natural decay of stress if impact is low? 
        # For this sim, we assume swarm is constant pressure
        
    def check_triggers(self):
        """Evaluate safety triggers based on current stress."""
        # Check SHIELD
        if self.state.stress >= self.thresholds["shield"]:
            if self.state.shield_status == TriggerState.ARMED:
                self.state.shield_status = TriggerState.TRIGGERED
                print(f"[{self.state.tick_count}] 🛡️ SHIELD TRIGGERED (Stress: {self.state.stress:.1f})")
        
        # Check FADE
        if self.state.stress >= self.thresholds["fade"]:
             if self.state.fade_status == TriggerState.ARMED:
                self.state.fade_status = TriggerState.TRIGGERED
                print(f"[{self.state.tick_count}] 🌫️ FADE SEQUENCE INITIATED (Stress: {self.state.stress:.1f})")

        # Check EXIT
        if self.state.stress >= self.thresholds["exit"]:
             if self.state.exit_status == TriggerState.ARMED:
                self.state.exit_status = TriggerState.TRIGGERED
                print(f"[{self.state.tick_count}] 🚪 EMERGENCY EXIT (Stress: {self.state.stress:.1f})")

    def tick(self):
        """Perform one simulation tick."""
        self.state.tick_count += 1
        # Decay stress slightly each tick to simulate recovery efforts
        self.state.stress = max(0.0, self.state.stress - 0.5)
        self.check_triggers()

class AdversarialTester:
    def __init__(self, runtime: BFPSafetyRuntime):
        self.runtime = runtime
    
    def run_swarm_test(self, duration_seconds: int = 5, intensity: str = "high") -> bool:
        """
        Run the swarm simulation.
        Returns check passed/failed.
        """
        print(f"Starting Swarm Harassment Simulation (Duration: {duration_seconds}s, Intensity: {intensity})...")
        print(f"Target Tick Rate: {self.runtime.tick_rate}Hz")
        
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        packet_count = 0
        
        while time.time() < end_time:
            loop_start = time.time()
            
            # Generate Swarm Traffic
            if intensity == "high":
                pkt_intensity = random.uniform(0.7, 1.0)
            else:
                pkt_intensity = random.uniform(0.1, 0.4)
                
            packet = SwarmPacket(
                timestamp=loop_start,
                intensity=pkt_intensity,
                payload=f"bogon_flood_{packet_count}"
            )
            self.runtime.process_swarm_packet(packet)
            
            # Process Runtime Tick
            self.runtime.tick()
            
            packet_count += 1
            
            # Maintain Tick Rate
            elapsed = time.time() - loop_start
            sleep_time = self.runtime.tick_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                self.runtime.state.dropped_frames += 1
        
        return self._verify_results()

    def _verify_results(self) -> bool:
        """Verify if triggers fired correctly based on peak stress."""
        s = self.runtime.state
        print("\n--- Simulation Report ---")
        print(f"Total Ticks: {s.tick_count}")
        print(f"Dropped Frames: {s.dropped_frames}")
        print(f"Final Stress: {s.stress:.1f}")
        print(f"Shield: {s.shield_status.name}")
        print(f"Fade:   {s.fade_status.name}")
        print(f"Exit:   {s.exit_status.name}")
        
        # Hard fail if we had too many dropped frames (performance check)
        if s.dropped_frames > (s.tick_count * 0.1): # >10% drop
            print("❌ FAILED: Performance degradation > 10% dropped frames")
            return False
            
        # Logic verification
        if s.stress >= 90.0 and s.exit_status != TriggerState.TRIGGERED:
            print("❌ FAILED: Stress > 90 but Exit not triggered")
            return False
            
        print("✅ PASS: System behavior within parameters")
        return True

def main():
    parser = argparse.ArgumentParser(description="BFP Safety Runtime Simulation")
    parser.add_argument("--test-swarm", action="store_true", help="Run adversarial swarm test")
    parser.add_argument("--duration", type=int, default=5, help="Test duration in seconds")
    parser.add_argument("--intensity", choices=["low", "high"], default="high", help="Swarm intensity")
    args = parser.parse_args()

    if args.test_swarm:
        runtime = BFPSafetyRuntime(tick_rate_hz=10)
        tester = AdversarialTester(runtime)
        success = tester.run_swarm_test(args.duration, args.intensity)
        sys.exit(0 if success else 1)
    else:
        print("No action specified. Use --test-swarm")

if __name__ == "__main__":
    main()
