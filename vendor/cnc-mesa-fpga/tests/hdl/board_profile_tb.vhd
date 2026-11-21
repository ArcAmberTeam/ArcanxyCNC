library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.IDROMConst.all;
use work.i92_x9card.all;
use work.PIN_ZHULONG_V2_34.all;

entity board_profile_tb is end;
architecture test of board_profile_tb is
begin
    process
    begin
        assert IOWidth = 34 and FPGASize = 9 and FPGAPins = 144 severity failure;
        assert ModuleID(3).GTag = QCountTag and ModuleID(3).NumInstances = x"03" severity failure;
        assert ModuleID(4).GTag = PWMTag and ModuleID(4).NumInstances = x"01" severity failure;
        assert ModuleID(5).GTag = SSerialTag and ModuleID(5).NumInstances = x"01" severity failure;
        assert ModuleID(6).GTag = StepGenTag and ModuleID(6).NumInstances = x"06" severity failure;
        assert PinDesc(0) = (IOPortTag & x"00" & SSerialTag & SSerialRX0Pin) severity failure;
        assert PinDesc(1) = (IOPortTag & x"00" & SSerialTag & SSerialTX0Pin) severity failure;
        assert PinDesc(2) = (IOPortTag & x"00" & SSerialTag & SSerialRX1Pin) severity failure;
        assert PinDesc(3) = (IOPortTag & x"00" & SSerialTag & SSerialTX1Pin) severity failure;
        for channel in 0 to 5 loop
            assert PinDesc(4 + channel*2) = (IOPortTag & std_logic_vector(to_unsigned(channel, 8)) & StepGenTag & StepGenStepPin) severity failure;
            assert PinDesc(5 + channel*2) = (IOPortTag & std_logic_vector(to_unsigned(channel, 8)) & StepGenTag & StepGenDirPin) severity failure;
        end loop;
        assert PinDesc(16) = (IOPortTag & x"00" & PWMTag & PWMAOutPin) severity failure;
        for gpio in 17 to 24 loop
            assert PinDesc(gpio) = (IOPortTag & x"00" & NullTag & x"00") severity failure;
        end loop;
        for channel in 0 to 2 loop
            assert PinDesc(25 + channel*3) = (IOPortTag & std_logic_vector(to_unsigned(channel, 8)) & QCountTag & QCountQAPin) severity failure;
            assert PinDesc(26 + channel*3) = (IOPortTag & std_logic_vector(to_unsigned(channel, 8)) & QCountTag & QCountQBPin) severity failure;
            assert PinDesc(27 + channel*3) = (IOPortTag & std_logic_vector(to_unsigned(channel, 8)) & QCountTag & QCountIdxPin) severity failure;
        end loop;
        for gpio in 34 to MaxPins - 1 loop
            assert PinDesc(gpio) = emptypin severity failure;
        end loop;
        report "Zhulong V2 board IDROM and all 34 GPIO mappings passed";
        std.env.stop;
        wait;
    end process;
end architecture;
