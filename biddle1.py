import math

# Epsilon for avoiding division by zero
EPSILON = 1e-9

def get_float_input(prompt_text, default_value):
    """Gets float input from the user, with a default value."""
    while True:
        try:
            user_input = input(f"{prompt_text} (default: {default_value}): ")
            if not user_input:
                return default_value
            return float(user_input)
        except ValueError:
            print("Invalid input. Please enter a number.")

def calculate_battle_outcomes():
    """
    Calculates and prints battle outcomes based on Biddle's model.
    """
    print("Please provide the input variables for the model.")
    print("Default values are based on Biddle's Appendix (e.g., Table A.1, Fig A.2 column where applicable).\n")

    # --- Input Variables with Defaults ---
    # Sources for defaults: equations.docx[cite: 1, 2, 3], 8 appendix.pdf (Table A.1, Fig A.2 col) [cite: 148]
    # and text (e.g. source 163 for d, fr; source 238 for Va)

    R = get_float_input("Invader troop strength (R)", 1250000) # [cite: 1, 148]
    B = get_float_input("Defender troop strength (B)", 1000000) # [cite: 1, 148]
    YR = get_float_input("Invader's mean weapon introduction year (YR) (e.g., 1910)", 1910) # [cite: 1, 148]
    YB = get_float_input("Defender's mean weapon introduction year (YB) (e.g., 1910)", 1910) # [cite: 1, 148]
    d = get_float_input("Depth of defender's forward positions (km) (d)", 15) # [cite: 1, 163]
    fr = get_float_input("Fraction of defender's troops in mobile reserve (fr)", 0.4) # [cite: 1, 163]
    fe = get_float_input("Fraction of defender's forward garrison exposed (fe)", 0.0) # [cite: 1, 148]
    Vr = get_float_input("Velocity of defender's reserve movements (km/day) (Vr)", 100) # [cite: 1, 148]
    Va = get_float_input("Velocity of invader's assault (km/day) (Va)", 4.5) # [cite: 1, 148, 238]
    wa = get_float_input("Invader's assault frontage (km) (wa)", 25) # [cite: 1, 148]
    wth = get_float_input("Theater frontage overall (km) (wth)", 500) # [cite: 1, 148]

    k1 = get_float_input("k1 (invaders one defender can halt)", 2.5) # [cite: 1, 148]
    k2 = get_float_input("k2 (fit parameter for Ps)", 0.01) # [cite: 2, 148]
    k3 = get_float_input("k3 (invaders to pin one defender)", 0.4) # [cite: 2, 148]
    k4 = get_float_input("k4 (fit parameter for rho1)", 0.5) # [cite: 2, 148]
    k5 = get_float_input("k5 (invader off-axis casualties)", 200000) # [cite: 2, 148]
    k6 = get_float_input("k6 (defender off-axis casualties)", 200000) # [cite: 2, 148] (Not used for requested outputs but included for completeness)
    k7 = get_float_input("k7 (fit parameter for Ca)", 5) # [cite: 2, 148]
    k8 = get_float_input("k8 (invader casualties per defender/day at zero Va)", 0.1) # [cite: 2, 148]
    k9 = get_float_input("k9 (invader flank defenders required parameter)", 0.01) # [cite: 3, 148]

    # --- Parameter Validation for Denominators ---
    if wth <= 0:
        print("Error: Theater frontage (wth) must be positive.")
        return
    if d <= 0:
        print("Error: Depth of defender's positions (d) must be positive.")
        return
    # Vr can be 0, will be handled in logic.

    # --- Calculations ---

    # A.1, A.2: Technology Indices [cite: 5]
    # (Ensuring YR, YB are >= 1900 based on time period of interest 1900-2020 [cite: 4])
    if YR < 1900: YR = 1900; print("Warning: YR was < 1900, set to 1900.")
    if YB < 1900: YB = 1900; print("Warning: YB was < 1900, set to 1900.")
    TR = (YR - 1900) / 10.0
    TB = (YB - 1900) / 10.0

    # A.3, A.4: Dyadic Technological Balance [cite: 7]
    # Add EPSILON to avoid division by zero if TR or TB is 0.
    TC = (TB**2) / (TR + EPSILON if TR == 0 else TR)
    TR_squared = TR**2 # Calculate TR^2 once
    T_rho = TR_squared / (TB + EPSILON if TB == 0 else TB)


    # A.5: Fraction of moving reserves surviving (Ps) [cite: 12]
    # Handling TR for Ps:
    # If TR = 0, assume Ps = 0 (no survival with zero tech).
    # If 0 < TR < 1, TR^(-k2*Vr) > 1. Clamp Ps to 1.0 as it's a fraction[cite: 8].
    # Otherwise, use the formula.
    # Exponent is -k2 * Vr
    exp_ps = -k2 * Vr
    if TR == 0:
        Ps = 0.0
        print("Warning: TR is 0 (YR=1900), Ps set to 0.")
    else:
        try:
            Ps_calculated = math.pow(TR, exp_ps)
            if Ps_calculated > 1.0 and TR < 1.0: # Check if TR < 1 caused Ps > 1
                # This case occurs if 0 < TR < 1, making TR^negative_exponent > 1
                Ps = 1.0
                print(f"Warning: Ps calculated as {Ps_calculated:.4f} (due to TR < 1), clamped to 1.0.")
            elif Ps_calculated < 0: # Should not happen with TR > 0
                Ps = 0.0
                print(f"Warning: Ps calculated as {Ps_calculated:.4f}, clamped to 0.0.")
            else:
                Ps = Ps_calculated
        except ValueError: # e.g. negative TR to non-integer power, though TR should be >=0
            Ps = 0.0
            print("Warning: Could not calculate Ps due to math error (e.g. TR invalid for pow), Ps set to 0.")
        except OverflowError:
             Ps = 0.0 # if TR is very small positive and exp_ps is very negative
             print("Warning: Ps calculation resulted in overflow (TR likely too small), Ps set to 0.")


    # A.6: Max attackers one defender can halt (H) [cite: 16]
    H = k1 * (1 - fe)

    # A.7: Linear density of flank defenders (rho1) [cite: 20]
    # Using PDF version of formula: rho1 = (k9 * B * fr * Ps) / (T_rho**k4) [cite: 102]
    # Original docx was rho1 = k9 * B * fr * Ps * T_rho * k4
    if T_rho == 0 and k4 > 0: # Avoid T_rho=0 in denominator if k4 > 0
        rho1 = float('inf') if k9 * B * fr * Ps > 0 else 0 # Effectively infinite density needed or zero if no force
        print("Warning: T_rho is 0, rho1 might be unrealistic (inf or 0).")
    elif T_rho < 0 and k4 != int(k4): # Avoid complex numbers from negative base to fractional power
        rho1 = 0 # Or handle as error, this case is unlikely with TR,TB >=0
        print("Warning: T_rho is negative, rho1 calculation with fractional k4 problematic, set to 0.")
    else:
        denominator_rho1 = math.pow(T_rho, k4) if T_rho >=0 else math.nan # handle T_rho < 0 cautiously
        if denominator_rho1 == 0:
            rho1 = float('inf') if k9 * B * fr * Ps > 0 else 0
            print("Warning: T_rho^k4 is 0, rho1 might be unrealistic (inf or 0).")
        else:
            rho1 = (k9 * B * fr * Ps) / (denominator_rho1 + EPSILON if denominator_rho1 == 0 else denominator_rho1)


    # A.8: Linear density of invader forces to pin defenders (rho2) [cite: 24]
    rho2 = (k3 * B * (1 - fr)) / wth # wth validated > 0

    # A.9: Invader's initial troop strength at point of attack (r0) [cite: 26]
    r0 = R - rho2 * (wth - wa)

    # A.10: Defender's initial troop strength at point of attack (b0) [cite: 28]
    b0 = (B * (1 - fr) * wa) / (wth * d) # wth, d validated > 0

    # A.11: Invader's casualties per km gained (Ca) [cite: 32]
    Ca = k7 * (1 - fe) * TC * b0 * (Va + k8)

    # A.12: Change in invader strength (delta_r) [cite: 37]
    delta_r = Ca * Va + 2 * rho1 * Va

    # A.14: Change in defender strength (delta_b_reinforcing) [cite: 41]
    # This is the rate if 0 < t < wth/Vr
    if Vr == 0:
        delta_b_reinforcing = 0.0
        wth_div_Vr = float('inf')
    else:
        delta_b_reinforcing = (B * fr * Vr * Ps) / wth
        wth_div_Vr = wth / Vr

    # A.17: Campaign duration (t_star) [cite: 49]
    t_star_numerator_case1 = r0 - H * b0
    t_star_denominator_case1 = delta_r + H * delta_b_reinforcing

    if t_star_denominator_case1 == 0:
        # If rate of convergence is zero
        if t_star_numerator_case1 > 0: # Attacker stronger, defender not reinforcing or attacker not attriting enough
            t_star = float('inf')
            print("Warning: Denominator for t* (case 1) is zero, r0 > Hb0. Offensive potentially unending (t* = inf).")
        else: # Attacker already weaker or equal
            t_star = 0.0
            print("Warning: Denominator for t* (case 1) is zero, r0 <= Hb0. Offensive halted or never starts (t* = 0).")

    else:
        t_candidate1 = t_star_numerator_case1 / t_star_denominator_case1
        
        if t_candidate1 < 0: # If r0 < H*b0 initially
            t_star = 0.0
        elif t_candidate1 < wth_div_Vr:
            t_star = t_candidate1
        else:
            # Second case for t_star
            t_star_numerator_case2 = r0 - H * b0 - H * B * fr * Ps
            if delta_r == 0:
                if t_star_numerator_case2 > 0:
                    t_star = float('inf')
                    print("Warning: delta_r is zero for t* (case 2), numerator > 0. Offensive potentially unending (t* = inf).")
                else:
                    t_star = 0.0 # Halted or never starts effectively
                    print("Warning: delta_r is zero for t* (case 2), numerator <= 0. Offensive halted (t* = 0).")
            else:
                t_star_candidate2 = t_star_numerator_case2 / delta_r
                t_star = t_star_candidate2 if t_star_candidate2 >=0 else 0.0


    # A.18: Net penetration depth (G) [cite: 51]
    G = t_star * Va if t_star != float('inf') else float('inf')

    # A.19: Breakthrough [cite: 53]
    breakthrough = "Yes" if G > d and G != float('inf') else "No"
    if G == float('inf') and d != float('inf'): # Infinite penetration implies breakthrough if d is finite
        breakthrough = "Yes (Infinite Penetration)"


    # A.20: Invader Casualties (CR) [cite: 58]
    # "estimate casualties explicitly only for offensives that fail to break through" [cite: 55]
    # "where breakthrough and successful exploitation occur, capability is assumed to be high for invaders..." [cite: 56]
    # However, user asked for CR, so we calculate based on formula.
    if G == float('inf'):
        CR = float('inf')
    else:
        CR = Ca * G + k5


    # --- Outputs ---
    print("\n--- Calculated Outcomes ---")
    print(f"Weighted mean invader tech index (TR): {TR:.2f}")
    print(f"Weighted mean defender tech index (TB): {TB:.2f}")
    print(f"Dyadic tech balance at point of attack (TC): {TC:.2f}")
    print(f"Dyadic tech balance on flanks (T_rho): {T_rho:.2f}")
    print(f"Fraction of reserves surviving movement (Ps): {Ps:.4f}")
    print(f"Max attackers one defender can halt (H): {H:.2f}")
    print(f"Invader flank density required (rho1): {rho1:.2f} troops/km")
    print(f"Invader pinning density required (rho2): {rho2:.2f} troops/km")
    print(f"Invader strength at point of attack (r0): {r0:.0f} troops")
    print(f"Defender strength at point of attack (b0): {b0:.0f} troops")
    print(f"Change in invader strength per day (delta_r): {delta_r:.2f} troops/day")
    print(f"Change in defender strength per day (delta_b_reinforcing, if t < wth/Vr): {delta_b_reinforcing:.2f} troops/day")
    print(f"Campaign Duration (t*): {t_star:.2f} days" if t_star!=float('inf') else "Campaign Duration (t*): Infinite")
    
    print(f"\n--- Main Outputs ---")
    print(f"Invader Casualties per km gained (Ca): {Ca:.2f} casualties/km")
    if G != float('inf'):
        print(f"Territorial Gain (G): {G:.2f} km")
    else:
        print("Territorial Gain (G): Infinite")
    print(f"Breakthrough: {breakthrough}")
    if CR != float('inf'):
        print(f"Total Invader Casualties (CR): {CR:.0f} casualties")
    else:
        print("Total Invader Casualties (CR): Infinite")


if __name__ == "__main__":
    calculate_battle_outcomes()
