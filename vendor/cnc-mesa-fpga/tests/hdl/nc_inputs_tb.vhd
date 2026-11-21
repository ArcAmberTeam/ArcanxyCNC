library ieee;
use ieee.std_logic_1164.all;
use work.i92_x9card.all;

entity nc_inputs_tb is end;

architecture test of nc_inputs_tb is
    type bus_array is array (0 to IOPorts - 1) of std_logic_vector(31 downto 0);
    signal clk : std_logic := '0';
    signal pads : std_logic_vector(IOWidth - 1 downto 0);
    signal fpga_drive : std_logic_vector(IOWidth - 1 downto 0);
    signal external_levels : std_logic_vector(IOWidth - 1 downto 0) := (others => '0');
    signal read_enable : std_logic_vector(IOPorts - 1 downto 0) := (others => '0');
    signal read_bus : bus_array;
    signal load_output_invert : std_logic := '0';
begin
    clk <= not clk after 5 ns;
    pads <= fpga_drive;
    -- The observed board levels are stimulus, not a model of its analog pull-up.
    -- NC to GND: closed=0, open=1. The unmodified Mesa input must preserve this.
    pads <= external_levels;

    ports: for bank in 0 to IOPorts - 1 generate
        output_port: entity work.wordpr
            generic map (size => PortWidth, buswidth => 32)
            port map (
                clear => '0', clk => clk, ibus => (others => '1'), obus => open,
                loadport => '0', loadddr => '0', loadaltdatasrc => '0',
                loadopendrainmode => '0', loadinvert => load_output_invert,
                readddr => '0', altdata => (others => '0'),
                portdata => fpga_drive((bank + 1) * PortWidth - 1 downto bank * PortWidth)
            );
        input_port: entity work.wordrb
            generic map (size => PortWidth, buswidth => 32)
            port map (
                readport => read_enable(bank), obus => read_bus(bank),
                portdata => pads((bank + 1) * PortWidth - 1 downto bank * PortWidth)
            );
    end generate;

    process
        variable expected : std_logic_vector(31 downto 0);
        procedure check_reads is
        begin
            assert fpga_drive = (fpga_drive'range => 'Z')
                report "GPIO inputs must remain high impedance" severity failure;
            for bank in 0 to IOPorts - 1 loop
                read_enable <= (others => '0');
                read_enable(bank) <= '1';
                wait for 20 ns;
                expected := (others => '0');
                expected(PortWidth - 1 downto 0) :=
                    external_levels((bank + 1) * PortWidth - 1 downto bank * PortWidth);
                assert read_bus(bank) = expected
                    report "NC input inverted, misrouted or contaminated" severity failure;
                for other_bank in 0 to IOPorts - 1 loop
                    if other_bank /= bank then
                        assert read_bus(other_bank) = (31 downto 0 => 'Z')
                            report "Unselected input bank drove the bus" severity failure;
                    end if;
                end loop;
            end loop;
        end procedure;
    begin
        wait for 20 ns;
        check_reads;
        -- Output inversion is not input inversion, even if its register is set.
        load_output_invert <= '1';
        wait for 20 ns;
        load_output_invert <= '0';
        check_reads;
        for gpio in 20 to 22 loop
            external_levels(gpio) <= '1';
            wait for 20 ns;
            for sample in 1 to 10 loop
                check_reads;
            end loop;
            external_levels(gpio) <= '0';
            wait for 20 ns;
            check_reads;
        end loop;
        external_levels(22 downto 20) <= "111";
        wait for 20 ns;
        check_reads;
        external_levels(22 downto 20) <= "000";
        wait for 20 ns;
        check_reads;
        read_enable <= (others => '0');
        wait for 20 ns;
        for bank in 0 to IOPorts - 1 loop
            assert read_bus(bank) = (31 downto 0 => 'Z') severity failure;
        end loop;
        report "GPIO 20/21/22 NC levels, isolation and input mode passed";
        std.env.stop;
        wait;
    end process;
end architecture;
