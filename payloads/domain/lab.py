"""The only robot constructor in this package: PyLabRobot's Chatterbox simulation."""

import copy

from .protocol import TIP_CAPACITY, initial_state


class SimulatedLab:
    def __init__(self, plan):
        from pylabrobot.liquid_handling import LiquidHandler
        from pylabrobot.liquid_handling.backends import LiquidHandlerChatterboxBackend
        from pylabrobot.resources import (
            Cor_96_wellplate_360ul_Fb, PLT_CAR_L5AC_A00, TIP_CAR_480_A00,
            hamilton_96_tiprack_300uL_filter, set_tip_tracking, set_volume_tracking,
        )
        from pylabrobot.resources.hamilton import STARLetDeck

        set_tip_tracking(True)
        set_volume_tracking(True)
        self.lh = LiquidHandler(backend=LiquidHandlerChatterboxBackend(num_channels=1), deck=STARLetDeck())
        tip_carrier, plate_carrier = TIP_CAR_480_A00(name='tip_carrier'), PLT_CAR_L5AC_A00(name='plate_carrier')
        self.tips = hamilton_96_tiprack_300uL_filter(name='tips')
        tip_carrier[0] = self.tips
        self.lh.deck.assign_child_resource(tip_carrier, rails=1)
        self.plates = {}
        for index, name in enumerate(plan['plates']):
            plate_carrier[index] = self.plates[name] = Cor_96_wellplate_360ul_Fb(name=name)
        self.lh.deck.assign_child_resource(plate_carrier, rails=8)
        self.labels = initial_state(plan)
        for item in plan['liquids']:
            self.well(item['well']).tracker.set_volume(item['volume_ul'])
        self.tip_index = 0

    def well(self, address):
        plate, well = address.split('/')
        return self.plates[plate].get_item(well)

    async def setup(self):
        await self.lh.setup()

    async def stop(self):
        await self.lh.stop()

    def observe(self):
        value = copy.deepcopy(self.labels)
        for name, state in value['wells'].items():
            state['volume_ul'] = round(self.well(name).tracker.get_used_volume(), 6)
        value['tips_remaining'] = sum(spot.has_tip() for spot in self.tips.get_all_items())
        return value

    @property
    def tip_attached(self):
        return self.lh.head[0].has_tip

    async def fresh_tip(self):
        tip = self.tips.get_item(self.tip_index)
        await self.lh.pick_up_tips([tip], use_channels=[0])
        self.tip_index += 1
        return self.tip_index - 1

    async def perform(self, action, check, tick):
        """Execute one checked step. No model text is interpreted as Python or a URL."""
        kind = action['kind']

        async def observed(kind, label, **target):
            # Publish only after a tracker-confirmed command, and yield before
            # the next command so both halves of a mix are visible.
            await tick({'kind': kind, 'label': label, **target})
            check()

        check()
        if kind == 'transfer':
            remaining = action['volume_ul']
            source, destination = self.well(action['source']), self.well(action['destination'])
            while remaining > 1e-6:
                check()
                amount = min(TIP_CAPACITY, remaining)
                tip_index = await self.fresh_tip()
                await observed('pick_up_tip', 'Picked up a fresh tip', tip_index=tip_index)
                await self.lh.aspirate([source], vols=[amount], use_channels=[0])
                await observed('aspirate', f"Aspirated {amount:g} uL from {action['source']}", well=action['source'])
                await self.lh.dispense([destination], vols=[amount], use_channels=[0])
                labels = self.labels['wells']
                labels[action['destination']]['liquids'] = sorted(set(
                    labels[action['destination']]['liquids'] + labels[action['source']]['liquids']))
                await observed('dispense', f"Dispensed {amount:g} uL into {action['destination']}", well=action['destination'])
                await self.lh.discard_tips(use_channels=[0], allow_nonzero_volume=False)
                await observed('discard_tip', 'Discarded the used tip')
                remaining -= amount
        elif kind == 'mix':
            well = self.well(action['well'])
            tip_index = await self.fresh_tip()
            await observed('pick_up_tip', 'Picked up a fresh tip', tip_index=tip_index)
            for cycle in range(1, action['cycles'] + 1):
                check()
                await self.lh.aspirate([well], vols=[action['volume_ul']], use_channels=[0])
                await observed('aspirate', f"Mix {cycle}/{action['cycles']}: aspirated {action['volume_ul']:g} uL from {action['well']}",
                               well=action['well'])
                await self.lh.dispense([well], vols=[action['volume_ul']], use_channels=[0])
                await observed('dispense', f"Mix {cycle}/{action['cycles']}: dispensed {action['volume_ul']:g} uL into {action['well']}",
                               well=action['well'])
            await self.lh.discard_tips(use_channels=[0], allow_nonzero_volume=False)
            await observed('discard_tip', 'Discarded the used tip')
        elif kind == 'wait':
            # Time advances in the procedure ledger; no physical process is inferred.
            await observed('wait', f"Advanced {action['seconds']:g} virtual seconds")
        elif kind == 'check_volume':
            well = self.well(action['well'])
            volume = well.tracker.get_used_volume()
            await observed('check_volume', f"Checked {action['well']}: {volume:g} uL", well=action['well'])
            if not action['minimum_ul'] - 1e-6 <= volume <= action['maximum_ul'] + 1e-6:
                return {'passed': False, 'observed_ul': volume}
            return {'passed': True, 'observed_ul': volume}
        return {'passed': True}
