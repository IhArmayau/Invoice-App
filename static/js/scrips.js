function addRow() {
    const tableBody = document.querySelector('#itemsTable tbody');
    const row = document.createElement('tr');

    row.innerHTML = `
        <td><input type="text" name="item_name" required></td>
        <td><input type="number" name="item_qty" value="1" min="1"></td>
        <td><input type="number" name="item_price" value="0.00" step="0.01"></td>
        <td class="row-subtotal">0.00</td>
        <td><button type="button" class="remove-btn">Remove</button></td>
    `;

    tableBody.appendChild(row);

    // Add event listeners for inputs
    row.querySelector('[name="item_qty"]').addEventListener('input', calculateTotals);
    row.querySelector('[name="item_price"]').addEventListener('input', calculateTotals);
    row.querySelector('.remove-btn').addEventListener('click', function() {
        row.remove();
        calculateTotals();
    });

    calculateTotals();
}

function calculateTotals() {
    let subtotal = 0;
    document.querySelectorAll('#itemsTable tbody tr').forEach(row => {
        const qty = parseFloat(row.querySelector('[name="item_qty"]').value) || 0;
        const price = parseFloat(row.querySelector('[name="item_price"]').value) || 0;
        const rowSubtotal = qty * price;
        row.querySelector('.row-subtotal').innerText = rowSubtotal.toFixed(2);
        subtotal += rowSubtotal;
    });

    const taxRate = parseFloat(document.querySelector('[name="tax_rate"]').value) || 0;
    const discountRate = parseFloat(document.querySelector('[name="discount_rate"]').value) || 0;

    const tax = subtotal * (taxRate / 100);
    const discount = subtotal * (discountRate / 100);
    const total = subtotal + tax - discount;

    document.getElementById('subtotal').innerText = subtotal.toFixed(2);
    document.getElementById('tax').innerText = tax.toFixed(2);
    document.getElementById('discount').innerText = discount.toFixed(2);
    document.getElementById('total').innerText = total.toFixed(2);
}

// Event listeners for tax and discount inputs
document.querySelector('[name="tax_rate"]').addEventListener('input', calculateTotals);
document.querySelector('[name="discount_rate"]').addEventListener('input', calculateTotals);

// Initialize with one row
addRow();
